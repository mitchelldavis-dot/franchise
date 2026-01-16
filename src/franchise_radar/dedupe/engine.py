"""Lead deduplication engine."""

from typing import List, Dict, Any, Set, Optional
from collections import defaultdict

from fuzzywuzzy import fuzz
from loguru import logger
from sqlmodel import Session, select

from ..models import Lead, Evidence, Document


class DedupeEngine:
    """Engine for deduplicating leads across sources."""

    def __init__(self, session: Session):
        """Initialize dedupe engine.

        Args:
            session: Database session
        """
        self.session = session
        self.handle_similarity_threshold = 85
        self.text_similarity_threshold = 80

    def deduplicate_by_url(self, doc_ids: List[int]) -> Dict[str, List[int]]:
        """Group documents by exact URL match.

        Args:
            doc_ids: List of document IDs to dedupe

        Returns:
            Dict mapping URL to list of doc IDs
        """
        url_groups: Dict[str, List[int]] = defaultdict(list)

        for doc_id in doc_ids:
            doc = self.session.get(Document, doc_id)
            if doc and doc.url:
                url_groups[doc.url].append(doc_id)

        return url_groups

    def deduplicate_by_handle(
        self,
        doc_ids: List[int],
        excluded_urls: Set[str] = None,
    ) -> Dict[str, List[int]]:
        """Group documents by author handle with fuzzy matching.

        Args:
            doc_ids: List of document IDs to dedupe
            excluded_urls: URLs already grouped (to avoid double-counting)

        Returns:
            Dict mapping canonical handle to list of doc IDs
        """
        if excluded_urls is None:
            excluded_urls = set()

        handle_groups: Dict[str, List[int]] = defaultdict(list)
        handle_map: Dict[str, str] = {}  # Map similar handles to canonical

        for doc_id in doc_ids:
            doc = self.session.get(Document, doc_id)
            if not doc or not doc.author_handle or doc.url in excluded_urls:
                continue

            handle = doc.author_handle.lower().strip()

            # Check if similar to existing handle
            canonical = None
            for existing_handle in handle_map.keys():
                similarity = fuzz.ratio(handle, existing_handle)
                if similarity >= self.handle_similarity_threshold:
                    canonical = handle_map[existing_handle]
                    break

            if not canonical:
                canonical = handle
                handle_map[handle] = canonical

            handle_groups[canonical].append(doc_id)

        return handle_groups

    def deduplicate_by_text_similarity(
        self,
        doc_ids: List[int],
        excluded_urls: Set[str] = None,
    ) -> Dict[str, List[int]]:
        """Group documents by text similarity.

        Args:
            doc_ids: List of document IDs to dedupe
            excluded_urls: URLs already grouped

        Returns:
            Dict mapping group ID to list of doc IDs
        """
        if excluded_urls is None:
            excluded_urls = set()

        # Get document texts
        doc_texts: Dict[int, str] = {}
        for doc_id in doc_ids:
            doc = self.session.get(Document, doc_id)
            if doc and doc.url not in excluded_urls:
                # Use first 500 chars for similarity comparison
                text = (doc.title or "") + " " + (doc.body or "")
                doc_texts[doc_id] = text[:500].lower()

        # Group by similarity
        groups: Dict[str, List[int]] = defaultdict(list)
        processed: Set[int] = set()

        for doc_id, text in doc_texts.items():
            if doc_id in processed:
                continue

            # Start new group
            group_id = f"textgroup_{doc_id}"
            groups[group_id].append(doc_id)
            processed.add(doc_id)

            # Find similar documents
            for other_id, other_text in doc_texts.items():
                if other_id in processed:
                    continue

                similarity = fuzz.partial_ratio(text, other_text)
                if similarity >= self.text_similarity_threshold:
                    groups[group_id].append(other_id)
                    processed.add(other_id)

        return groups

    def create_canonical_lead(
        self,
        doc_ids: List[int],
        lead_type: str,
        score_results: Dict[int, Any],
    ) -> Optional[Lead]:
        """Create a canonical lead from a group of documents.

        Args:
            doc_ids: List of document IDs in this group
            lead_type: Type of lead (A or B)
            score_results: Dict mapping doc_id to ScoreResult

        Returns:
            Created Lead object
        """
        if not doc_ids:
            return None

        # Get documents
        docs = [self.session.get(Document, doc_id) for doc_id in doc_ids]
        docs = [d for d in docs if d]

        if not docs:
            return None

        # Aggregate data from all documents
        handles = set(d.author_handle for d in docs if d.author_handle)
        canonical_handle = list(handles)[0] if handles else None

        # Get best location info
        location_info = None
        for doc_id in doc_ids:
            if doc_id in score_results:
                extracted = score_results[doc_id].extracted_fields
                if extracted.get("location"):
                    location_info = extracted["location"]
                    if location_info.get("geo_confidence") == "high":
                        break

        # Calculate priority score (max score across all evidence)
        max_score = 0.0
        best_tier = "Researching"
        for doc_id in doc_ids:
            if doc_id in score_results:
                result = score_results[doc_id]
                if result.score > max_score:
                    max_score = result.score
                    best_tier = result.tier

        # Aggregate extracted fields
        all_budget_hints = set()
        all_timeline_hints = set()
        for doc_id in doc_ids:
            if doc_id in score_results:
                extracted = score_results[doc_id].extracted_fields
                all_budget_hints.update(extracted.get("budget_hints", []))
                all_timeline_hints.update(extracted.get("timeline_hints", []))

        # Create lead
        lead = Lead(
            lead_type=lead_type,
            canonical_handle=canonical_handle,
            location_text=location_info.get("location_text") if location_info else None,
            location_city=location_info.get("location_city") if location_info else None,
            location_state=location_info.get("location_state") if location_info else None,
            geo_confidence=location_info.get("geo_confidence") if location_info else None,
            geo_why=location_info.get("geo_why") if location_info else None,
            is_florida=location_info.get("is_florida", False) if location_info else False,
            priority_score=max_score,
            tier=best_tier,
            extracted_fields={
                "budget_hints": list(all_budget_hints),
                "timeline_hints": list(all_timeline_hints),
                "source_count": len(doc_ids),
            },
        )

        self.session.add(lead)
        self.session.commit()
        self.session.refresh(lead)

        # Create evidence records
        for doc_id in doc_ids:
            if doc_id in score_results:
                result = score_results[doc_id]
                doc = self.session.get(Document, doc_id)

                # Create snippet (first 300 chars)
                snippet = (doc.body or "")[:300]

                evidence = Evidence(
                    lead_id=lead.lead_id,
                    doc_id=doc_id,
                    snippet=snippet,
                    reasons=result.reasons,
                    score=result.score,
                    tier=result.tier,
                    extracted_fields=result.extracted_fields,
                )
                self.session.add(evidence)

        self.session.commit()

        logger.info(f"Created lead {lead.lead_id} with {len(doc_ids)} evidence items")
        return lead


def deduplicate_leads(
    session: Session,
    doc_ids: List[int],
    lead_type: str,
    score_results: Dict[int, Any],
) -> List[Lead]:
    """Deduplicate documents into canonical leads.

    Args:
        session: Database session
        doc_ids: List of document IDs to process
        lead_type: Type of lead (A or B)
        score_results: Dict mapping doc_id to ScoreResult

    Returns:
        List of created Lead objects
    """
    engine = DedupeEngine(session)
    leads = []

    # Step 1: Group by exact URL
    url_groups = engine.deduplicate_by_url(doc_ids)
    logger.info(f"Found {len(url_groups)} unique URLs")

    # Track URLs we've processed
    processed_urls = set()

    # Create leads from URL groups
    for url, group_doc_ids in url_groups.items():
        if len(group_doc_ids) > 0:
            lead = engine.create_canonical_lead(group_doc_ids, lead_type, score_results)
            if lead:
                leads.append(lead)
                processed_urls.add(url)

    # Step 2: Group remaining by handle
    handle_groups = engine.deduplicate_by_handle(doc_ids, excluded_urls=processed_urls)
    logger.info(f"Found {len(handle_groups)} unique handles")

    for handle, group_doc_ids in handle_groups.items():
        if len(group_doc_ids) > 0:
            lead = engine.create_canonical_lead(group_doc_ids, lead_type, score_results)
            if lead:
                leads.append(lead)
                # Mark these URLs as processed
                for doc_id in group_doc_ids:
                    doc = session.get(Document, doc_id)
                    if doc and doc.url:
                        processed_urls.add(doc.url)

    # Step 3: Group remaining by text similarity
    text_groups = engine.deduplicate_by_text_similarity(doc_ids, excluded_urls=processed_urls)
    logger.info(f"Found {len(text_groups)} text similarity groups")

    for group_id, group_doc_ids in text_groups.items():
        if len(group_doc_ids) > 0:
            lead = engine.create_canonical_lead(group_doc_ids, lead_type, score_results)
            if lead:
                leads.append(lead)

    logger.info(f"Created {len(leads)} total leads from {len(doc_ids)} documents")
    return leads
