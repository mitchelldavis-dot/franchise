"""RSS feed ingestion adapter."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

import feedparser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from .base import BaseAdapter, Document


class RSSAdapter(BaseAdapter):
    """Adapter for RSS feed ingestion."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize RSS adapter.

        Args:
            config: Configuration dict with 'feeds' list
        """
        super().__init__("rss", config)

    def validate_config(self) -> bool:
        """Validate RSS configuration."""
        feeds = self.config.get("feeds", [])
        if not feeds:
            self.logger.warning("No RSS feeds configured")
            return False

        for feed in feeds:
            if not isinstance(feed, dict) or "url" not in feed:
                self.logger.warning(f"Invalid feed config: {feed}")
                return False

        return True

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def ingest(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Document]:
        """Ingest entries from configured RSS feeds.

        Args:
            since: Only fetch entries after this time
            limit: Max entries per feed

        Returns:
            List of documents
        """
        feeds = self.config.get("feeds", [])
        documents = []

        for feed_config in feeds:
            feed_url = feed_config["url"]
            feed_name = feed_config.get("name", feed_url)

            try:
                self.logger.info(f"Fetching RSS feed: {feed_name}")

                # Fetch and parse feed
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(feed_url)
                    response.raise_for_status()
                    content = response.content

                parsed = feedparser.parse(content)

                # Process entries
                for entry in parsed.entries[:limit] if limit else parsed.entries:
                    # Parse published date
                    published_at = self._parse_date(entry)

                    # Filter by date if specified
                    if since and published_at and published_at < since:
                        continue

                    # Extract content
                    body = ""
                    if hasattr(entry, "summary"):
                        body = entry.summary
                    elif hasattr(entry, "content"):
                        body = entry.content[0].value if entry.content else ""
                    elif hasattr(entry, "description"):
                        body = entry.description

                    # Create document
                    doc = Document(
                        external_id=f"rss_{feed_name}_{entry.get('id', entry.link)}",
                        url=entry.get("link"),
                        author_handle=entry.get("author"),
                        title=entry.get("title"),
                        body=body,
                        published_at=published_at,
                        raw_json={
                            "feed_name": feed_name,
                            "feed_url": feed_url,
                            "entry_id": entry.get("id"),
                            "tags": entry.get("tags", []),
                        },
                    )
                    documents.append(doc)

                self.logger.info(f"Fetched {len(documents)} entries from {feed_name}")

            except Exception as e:
                self.logger.error(f"Error fetching RSS feed {feed_name}: {e}")
                continue

        self.logger.info(f"Total documents ingested from RSS: {len(documents)}")
        return documents

    def _parse_date(self, entry) -> Optional[datetime]:
        """Parse date from RSS entry."""
        # Try different date fields
        for field in ["published_parsed", "updated_parsed", "created_parsed"]:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except Exception:
                        pass

        return None
