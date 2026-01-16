"""Main scoring engine with explainable logic."""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from loguru import logger

from ..config import get_config


@dataclass
class ScoreResult:
    """Result of scoring a document."""
    score: float
    tier: str
    reasons: List[str] = field(default_factory=list)
    extracted_fields: Dict[str, Any] = field(default_factory=dict)
    breakdown: Dict[str, float] = field(default_factory=dict)


class ScoringEngine:
    """Explainable scoring engine for leads."""

    def __init__(self):
        """Initialize scoring engine."""
        self.config = get_config()
        self.weights = self.config.get_weights()
        self.thresholds = self.config.get_thresholds()
        self.proximity_window = self.config.get("scoring", {}).get("proximity_window", 10)

    def _get_phrases_with_weights(self, pack_names: List[str]) -> List[Dict[str, Any]]:
        """Get phrases from multiple packs with their weights."""
        phrases = []
        for pack_name in pack_names:
            pack = self.config.get_phrase_pack(pack_name)
            for item in pack:
                phrases.append(item)
        return phrases

    def _find_phrase_matches(self, text: str, phrases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find all phrase matches in text.

        Returns list of matches with phrase, weight, position, and context.
        """
        text_lower = text.lower()
        matches = []

        for phrase_item in phrases:
            phrase = phrase_item["phrase"].lower()
            weight = phrase_item.get("weight", 1)

            # Find all occurrences
            pattern = r'\b' + re.escape(phrase) + r'\b'
            for match in re.finditer(pattern, text_lower):
                start = match.start()
                end = match.end()

                # Get context (50 chars before and after)
                context_start = max(0, start - 50)
                context_end = min(len(text), end + 50)
                context = text[context_start:context_end].strip()

                matches.append({
                    "phrase": phrase,
                    "weight": weight,
                    "position": start,
                    "context": context,
                })

        return matches

    def _calculate_proximity_bonus(
        self,
        text: str,
        primary_phrases: List[str],
        secondary_phrases: List[str],
    ) -> float:
        """Calculate bonus for proximity of related phrases.

        E.g., "franchise" near "gym" or "my" near "gym"
        """
        text_lower = text.lower()
        words = text_lower.split()
        bonus = 0.0

        for i, word in enumerate(words):
            # Check if word contains any primary phrase
            for primary in primary_phrases:
                if primary in word:
                    # Look for secondary phrases within proximity window
                    window_start = max(0, i - self.proximity_window)
                    window_end = min(len(words), i + self.proximity_window + 1)
                    window = words[window_start:window_end]

                    for secondary in secondary_phrases:
                        if any(secondary in w for w in window):
                            bonus += 1.0

        return bonus

    def _check_question_format(self, text: str) -> bool:
        """Check if text is in question format."""
        question_patterns = [
            r'\bhow (do|can|to|much)\b',
            r'\bwhat\'?s?\b',
            r'\bwhere\b',
            r'\bwhen\b',
            r'\bwhy\b',
            r'\bwhich\b',
            r'\bany (recommendations|suggestions|advice)\b',
            r'\?',
        ]

        text_lower = text.lower()
        for pattern in question_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _check_first_person(self, text: str) -> bool:
        """Check for first-person intent indicators."""
        first_person_patterns = [
            r'\bI (want|need|\'m looking|am looking|\'m trying|am trying)\b',
            r'\bwe (want|need|are looking|\'re looking|are trying|\'re trying)\b',
            r'\bmy\b',
            r'\bour\b',
        ]

        text_lower = text.lower()
        for pattern in first_person_patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    def _calculate_freshness_boost(self, published_at: Optional[datetime]) -> float:
        """Calculate freshness boost based on recency."""
        if not published_at:
            return 0.0

        decay_days = self.config.get("scoring", {}).get("freshness_decay_days", 30)
        age_days = (datetime.utcnow() - published_at).days

        if age_days <= 1:
            return 1.0
        elif age_days <= 7:
            return 0.8
        elif age_days <= 30:
            return 0.5
        elif age_days <= decay_days:
            return 0.3
        else:
            return 0.1

    def _get_tier_from_score(self, score: float, lead_type: str) -> str:
        """Get tier based on score and thresholds."""
        if lead_type == "buyer":
            if score >= self.thresholds.get("buyer_ready", 80):
                return "Ready"
            elif score >= self.thresholds.get("buyer_comparing", 60):
                return "Comparing"
            else:
                return "Researching"
        else:  # owner_pain
            if score >= self.thresholds.get("owner_urgent", 80):
                return "Urgent"
            elif score >= self.thresholds.get("owner_serious_pain", 60):
                return "Serious Pain"
            else:
                return "Mild Pain"


def score_franchise_buyer(
    text: str,
    title: Optional[str] = None,
    source: str = "unknown",
    published_at: Optional[datetime] = None,
) -> ScoreResult:
    """Score franchise buyer intent.

    Args:
        text: Main text content
        title: Optional title
        source: Source name
        published_at: Publication datetime

    Returns:
        ScoreResult with score, tier, reasons, and breakdown
    """
    engine = ScoringEngine()
    config = engine.config

    # Combine title and text
    full_text = f"{title or ''} {text}"

    # Initialize score and breakdown
    base_score = 0.0
    breakdown = {}
    reasons = []
    extracted_fields = {}

    # 1. Find phrase matches
    buyer_high_phrases = engine._get_phrases_with_weights([
        "franchise_buyer_high",
        "franchise_buyer_medium",
    ])
    vertical_phrases = engine._get_phrases_with_weights(["fitness_verticals"])
    budget_phrases = engine._get_phrases_with_weights(["budget_signals"])
    timeline_phrases = engine._get_phrases_with_weights(["timeline_signals"])
    negative_phrases = engine._get_phrases_with_weights(["negative_phrases"])

    # Find matches
    buyer_matches = engine._find_phrase_matches(full_text, buyer_high_phrases)
    vertical_matches = engine._find_phrase_matches(full_text, vertical_phrases)
    budget_matches = engine._find_phrase_matches(full_text, budget_phrases)
    timeline_matches = engine._find_phrase_matches(full_text, timeline_phrases)
    negative_matches = engine._find_phrase_matches(full_text, negative_phrases)

    # Calculate phrase hit score
    phrase_score = sum(m["weight"] for m in buyer_matches)
    phrase_score += sum(m["weight"] for m in vertical_matches)

    if phrase_score > 0:
        breakdown["phrase_hits"] = phrase_score * engine.weights.get("phrase_hits", 1.0)
        base_score += breakdown["phrase_hits"]
        reasons.append(f"Found {len(buyer_matches)} franchise intent phrases")
        reasons.append(f"Found {len(vertical_matches)} fitness vertical mentions")

    # 2. Proximity bonus (franchise + gym/fitness terms close together)
    proximity_bonus = engine._calculate_proximity_bonus(
        full_text,
        ["franchise", "franchising"],
        ["gym", "fitness", "studio", "yoga", "pilates", "crossfit"],
    )
    if proximity_bonus > 0:
        breakdown["proximity_bonus"] = proximity_bonus * engine.weights.get("proximity_bonus", 0.3)
        base_score += breakdown["proximity_bonus"]
        reasons.append(f"Franchise terms near fitness terms ({int(proximity_bonus)} times)")

    # 3. Question format bonus
    if engine._check_question_format(full_text):
        breakdown["question_format"] = 5 * engine.weights.get("question_format", 0.2)
        base_score += breakdown["question_format"]
        reasons.append("Question format detected")

    # 4. First-person intent
    if engine._check_first_person(full_text):
        breakdown["first_person"] = 5 * engine.weights.get("first_person", 0.25)
        base_score += breakdown["first_person"]
        reasons.append("First-person intent detected")

    # 5. Budget signals
    if budget_matches:
        budget_score = sum(m["weight"] for m in budget_matches)
        breakdown["budget_signals"] = budget_score * engine.weights.get("budget_signals", 0.15)
        base_score += breakdown["budget_signals"]
        reasons.append(f"Budget signals found: {', '.join(m['phrase'] for m in budget_matches[:3])}")
        extracted_fields["budget_hints"] = [m["phrase"] for m in budget_matches]

    # 6. Timeline signals
    if timeline_matches:
        timeline_score = sum(m["weight"] for m in timeline_matches)
        breakdown["timeline_signals"] = timeline_score * engine.weights.get("timeline_signals", 0.2)
        base_score += breakdown["timeline_signals"]
        reasons.append(f"Timeline signals: {', '.join(m['phrase'] for m in timeline_matches[:3])}")
        extracted_fields["timeline_hints"] = [m["phrase"] for m in timeline_matches]

    # 7. Source weighting
    source_weights = config.get("scoring", {}).get("source_weights", {})
    source_weight = source_weights.get(source, 1.0)
    if source_weight != 1.0:
        breakdown["source_weight_multiplier"] = source_weight
        base_score *= source_weight
        reasons.append(f"Source weight: {source_weight}")

    # 8. Freshness boost
    freshness = engine._calculate_freshness_boost(published_at)
    if freshness > 0:
        freshness_points = freshness * 5 * engine.weights.get("freshness_boost", 0.1)
        breakdown["freshness_boost"] = freshness_points
        base_score += freshness_points
        if published_at:
            age = (datetime.utcnow() - published_at).days
            reasons.append(f"Freshness boost: {age} days old")

    # 9. Apply negative phrase penalties
    if negative_matches:
        penalty = sum(m.get("weight", 0) for m in negative_matches)
        breakdown["negative_penalty"] = penalty
        base_score += penalty  # weight is already negative
        reasons.append(f"Penalty for exclusion phrases: {penalty}")

    # 10. Must have both franchise intent AND fitness context
    has_franchise_intent = len(buyer_matches) > 0
    has_fitness_context = len(vertical_matches) > 0

    if not (has_franchise_intent and has_fitness_context):
        base_score *= 0.1  # Severe penalty
        reasons.append("QUALIFICATION FAILED: Missing franchise intent or fitness context")

    # Cap score at 100
    final_score = min(100.0, max(0.0, base_score))

    # Get tier
    tier = engine._get_tier_from_score(final_score, "buyer")

    return ScoreResult(
        score=final_score,
        tier=tier,
        reasons=reasons,
        extracted_fields=extracted_fields,
        breakdown=breakdown,
    )


def score_owner_pain(
    text: str,
    title: Optional[str] = None,
    source: str = "unknown",
    published_at: Optional[datetime] = None,
) -> ScoreResult:
    """Score gym/studio owner pain signals.

    Args:
        text: Main text content
        title: Optional title
        source: Source name
        published_at: Publication datetime

    Returns:
        ScoreResult with score, tier, reasons, and breakdown
    """
    engine = ScoringEngine()
    config = engine.config

    # Combine title and text
    full_text = f"{title or ''} {text}"

    # Initialize
    base_score = 0.0
    breakdown = {}
    reasons = []
    extracted_fields = {}

    # Get phrase packs
    pain_high_phrases = engine._get_phrases_with_weights([
        "owner_pain_high",
        "owner_pain_medium",
    ])
    vertical_phrases = engine._get_phrases_with_weights(["fitness_verticals"])
    ownership_phrases = engine._get_phrases_with_weights(["ownership_indicators"])
    negative_phrases = engine._get_phrases_with_weights(["negative_phrases"])

    # Find matches
    pain_matches = engine._find_phrase_matches(full_text, pain_high_phrases)
    vertical_matches = engine._find_phrase_matches(full_text, vertical_phrases)
    ownership_matches = engine._find_phrase_matches(full_text, ownership_phrases)
    negative_matches = engine._find_phrase_matches(full_text, negative_phrases)

    # 1. Pain phrase hits
    pain_score = sum(m["weight"] for m in pain_matches)
    if pain_score > 0:
        breakdown["phrase_hits"] = pain_score * engine.weights.get("phrase_hits", 1.0)
        base_score += breakdown["phrase_hits"]
        reasons.append(f"Found {len(pain_matches)} pain indicators")

    # 2. Ownership indicators (critical for owner pain leads)
    ownership_score = sum(m["weight"] for m in ownership_matches)
    if ownership_score > 0:
        breakdown["ownership_indicators"] = ownership_score * engine.weights.get("ownership_indicators", 0.3)
        base_score += breakdown["ownership_indicators"]
        reasons.append(f"Ownership signals: {', '.join(m['phrase'] for m in ownership_matches[:3])}")

    # 3. Proximity bonus (ownership terms near pain terms)
    proximity_bonus = engine._calculate_proximity_bonus(
        full_text,
        ["my", "our", "own"],
        ["gym", "studio", "business", "members", "clients"],
    )
    if proximity_bonus > 0:
        breakdown["proximity_bonus"] = proximity_bonus * engine.weights.get("proximity_bonus", 0.3)
        base_score += breakdown["proximity_bonus"]
        reasons.append(f"Ownership terms near business terms ({int(proximity_bonus)} times)")

    # 4. Question format
    if engine._check_question_format(full_text):
        breakdown["question_format"] = 5 * engine.weights.get("question_format", 0.2)
        base_score += breakdown["question_format"]
        reasons.append("Question format detected")

    # 5. First-person intent
    if engine._check_first_person(full_text):
        breakdown["first_person"] = 5 * engine.weights.get("first_person", 0.25)
        base_score += breakdown["first_person"]
        reasons.append("First-person intent detected")

    # 6. Fitness vertical context
    if vertical_matches:
        vertical_score = sum(m["weight"] for m in vertical_matches)
        breakdown["vertical_context"] = vertical_score * 0.5
        base_score += breakdown["vertical_context"]
        reasons.append(f"Fitness vertical: {', '.join(m['phrase'] for m in vertical_matches[:3])}")

    # 7. Source weighting
    source_weights = config.get("scoring", {}).get("source_weights", {})
    source_weight = source_weights.get(source, 1.0)
    if source_weight != 1.0:
        breakdown["source_weight_multiplier"] = source_weight
        base_score *= source_weight

    # 8. Freshness boost
    freshness = engine._calculate_freshness_boost(published_at)
    if freshness > 0:
        freshness_points = freshness * 5 * engine.weights.get("freshness_boost", 0.1)
        breakdown["freshness_boost"] = freshness_points
        base_score += freshness_points
        if published_at:
            age = (datetime.utcnow() - published_at).days
            reasons.append(f"Freshness: {age} days old")

    # 9. Negative penalties
    if negative_matches:
        penalty = sum(m.get("weight", 0) for m in negative_matches)
        breakdown["negative_penalty"] = penalty
        base_score += penalty
        reasons.append(f"Penalty: {penalty}")

    # 10. Qualification: must have ownership indicators AND pain signals
    has_ownership = len(ownership_matches) > 0
    has_pain = len(pain_matches) > 0

    if not (has_ownership and has_pain):
        base_score *= 0.1
        reasons.append("QUALIFICATION FAILED: Missing ownership indicators or pain signals")

    # Cap score
    final_score = min(100.0, max(0.0, base_score))

    # Get tier
    tier = engine._get_tier_from_score(final_score, "owner")

    return ScoreResult(
        score=final_score,
        tier=tier,
        reasons=reasons,
        extracted_fields=extracted_fields,
        breakdown=breakdown,
    )
