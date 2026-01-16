"""Manual import system for CSV/JSON data."""

import csv
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from loguru import logger

from .base import BaseAdapter, Document


class ManualImportAdapter(BaseAdapter):
    """Adapter for manual CSV/JSON imports."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize manual import adapter.

        Args:
            config: Configuration dict
        """
        super().__init__("manual_import", config)

    def validate_config(self) -> bool:
        """Validate configuration."""
        return True

    async def ingest(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Document]:
        """Not used for manual imports."""
        return []

    def import_from_csv(self, file_path: str, source_name: str = "manual") -> List[Document]:
        """Import documents from CSV file.

        Expected CSV columns:
        - url (required)
        - handle (optional)
        - title (optional)
        - body (required)
        - published_at (optional, ISO format)
        - context (optional, JSON string with extra data)

        Args:
            file_path: Path to CSV file
            source_name: Name for this import source

        Returns:
            List of documents
        """
        documents = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for i, row in enumerate(reader):
                    # Validate required fields
                    if not row.get("url") or not row.get("body"):
                        self.logger.warning(f"Skipping row {i}: missing url or body")
                        continue

                    # Parse published date
                    published_at = None
                    if row.get("published_at"):
                        try:
                            published_at = datetime.fromisoformat(row["published_at"])
                        except Exception:
                            self.logger.warning(f"Could not parse date for row {i}")

                    # Parse context
                    context = {}
                    if row.get("context"):
                        try:
                            context = json.loads(row["context"])
                        except Exception:
                            self.logger.warning(f"Could not parse context for row {i}")

                    # Create document
                    doc = Document(
                        external_id=f"manual_{source_name}_{row['url']}",
                        url=row["url"],
                        author_handle=row.get("handle"),
                        title=row.get("title"),
                        body=row["body"],
                        published_at=published_at,
                        raw_json={
                            "source_name": source_name,
                            "import_file": file_path,
                            "context": context,
                        },
                    )
                    documents.append(doc)

            self.logger.info(f"Imported {len(documents)} documents from {file_path}")

        except Exception as e:
            self.logger.error(f"Error importing CSV {file_path}: {e}")

        return documents

    def import_from_json(self, file_path: str, source_name: str = "manual") -> List[Document]:
        """Import documents from JSON file.

        Expected JSON structure:
        [
            {
                "url": "...",
                "handle": "...",
                "title": "...",
                "body": "...",
                "published_at": "...",
                "context": {...}
            },
            ...
        ]

        Args:
            file_path: Path to JSON file
            source_name: Name for this import source

        Returns:
            List of documents
        """
        documents = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if not isinstance(data, list):
                self.logger.error("JSON file must contain a list of objects")
                return []

            for i, item in enumerate(data):
                # Validate required fields
                if not item.get("url") or not item.get("body"):
                    self.logger.warning(f"Skipping item {i}: missing url or body")
                    continue

                # Parse published date
                published_at = None
                if item.get("published_at"):
                    try:
                        published_at = datetime.fromisoformat(item["published_at"])
                    except Exception:
                        self.logger.warning(f"Could not parse date for item {i}")

                # Create document
                doc = Document(
                    external_id=f"manual_{source_name}_{item['url']}",
                    url=item["url"],
                    author_handle=item.get("handle"),
                    title=item.get("title"),
                    body=item["body"],
                    published_at=published_at,
                    raw_json={
                        "source_name": source_name,
                        "import_file": file_path,
                        "context": item.get("context", {}),
                    },
                )
                documents.append(doc)

            self.logger.info(f"Imported {len(documents)} documents from {file_path}")

        except Exception as e:
            self.logger.error(f"Error importing JSON {file_path}: {e}")

        return documents

    @staticmethod
    def get_template_csv() -> str:
        """Get template CSV content for manual imports.

        Returns:
            CSV template as string
        """
        return """url,handle,title,body,published_at,context
https://example.com/post1,john_doe,Looking for gym franchise,I'm interested in buying a gym franchise in Miami. Budget around $200k. Any recommendations?,2024-01-15T10:00:00,"{\"platform\": \"quora\"}"
https://example.com/post2,jane_smith,Need marketing help,My yoga studio in Tampa is struggling with lead generation. Facebook ads stopped working.,2024-01-16T14:30:00,"{\"platform\": \"facebook\"}"
"""

    @staticmethod
    def get_template_json() -> str:
        """Get template JSON content for manual imports.

        Returns:
            JSON template as string
        """
        return json.dumps([
            {
                "url": "https://example.com/post1",
                "handle": "john_doe",
                "title": "Looking for gym franchise",
                "body": "I'm interested in buying a gym franchise in Miami. Budget around $200k. Any recommendations?",
                "published_at": "2024-01-15T10:00:00",
                "context": {"platform": "quora"}
            },
            {
                "url": "https://example.com/post2",
                "handle": "jane_smith",
                "title": "Need marketing help",
                "body": "My yoga studio in Tampa is struggling with lead generation. Facebook ads stopped working.",
                "published_at": "2024-01-16T14:30:00",
                "context": {"platform": "facebook"}
            }
        ], indent=2)
