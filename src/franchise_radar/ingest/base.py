"""Base adapter class for ingestion."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger


@dataclass
class Document:
    """Normalized document from any source."""
    external_id: str
    url: Optional[str]
    author_handle: Optional[str]
    title: Optional[str]
    body: str
    published_at: Optional[datetime]
    raw_json: Dict[str, Any]


class BaseAdapter(ABC):
    """Base class for all ingestion adapters."""

    def __init__(self, source_name: str, config: Dict[str, Any]):
        """Initialize adapter.

        Args:
            source_name: Name of the source
            config: Configuration dict for this source
        """
        self.source_name = source_name
        self.config = config
        self.logger = logger.bind(source=source_name)

    @abstractmethod
    async def ingest(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Document]:
        """Ingest documents from source.

        Args:
            since: Only ingest documents published after this time
            limit: Maximum number of documents to ingest

        Returns:
            List of normalized documents
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate that configuration is correct.

        Returns:
            True if config is valid
        """
        pass

    def _create_document(
        self,
        external_id: str,
        url: Optional[str],
        author_handle: Optional[str],
        title: Optional[str],
        body: str,
        published_at: Optional[datetime],
        raw_json: Dict[str, Any],
    ) -> Document:
        """Create a normalized document."""
        return Document(
            external_id=external_id,
            url=url,
            author_handle=author_handle,
            title=title,
            body=body,
            published_at=published_at,
            raw_json=raw_json,
        )
