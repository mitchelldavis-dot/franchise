"""YouTube ingestion adapter using official API."""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from .base import BaseAdapter, Document


class YouTubeAdapter(BaseAdapter):
    """Adapter for YouTube using official Data API."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize YouTube adapter.

        Args:
            config: Configuration dict
        """
        super().__init__("youtube", config)
        self.youtube = None
        self._init_youtube()

    def _init_youtube(self):
        """Initialize YouTube API client."""
        api_key = os.getenv("YOUTUBE_API_KEY")

        if not api_key:
            self.logger.warning("YouTube API key not found. YouTube ingestion disabled.")
            return

        try:
            self.youtube = build("youtube", "v3", developerKey=api_key)
            self.logger.info("YouTube API initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube API: {e}")
            self.youtube = None

    def validate_config(self) -> bool:
        """Validate YouTube configuration."""
        if not self.youtube:
            return False

        queries = self.config.get("queries", [])
        if not queries:
            self.logger.warning("No YouTube queries configured")
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
        """Ingest videos from configured queries.

        Args:
            since: Only fetch videos published after this time (default: 7 days ago)
            limit: Max videos per query (default: 50)

        Returns:
            List of documents
        """
        if not self.youtube:
            self.logger.warning("YouTube API not initialized")
            return []

        if since is None:
            since = datetime.utcnow() - timedelta(days=7)

        if limit is None:
            limit = 50

        queries = self.config.get("queries", [])
        documents = []

        for query in queries:
            try:
                self.logger.info(f"Searching YouTube for: {query}")

                # Search for videos
                search_response = self.youtube.search().list(
                    q=query,
                    type="video",
                    part="id,snippet",
                    maxResults=min(limit, 50),  # API max is 50
                    publishedAfter=since.isoformat() + "Z",
                    order="date",
                ).execute()

                # Process results
                for item in search_response.get("items", []):
                    video_id = item["id"]["videoId"]
                    snippet = item["snippet"]

                    # Create document for video
                    doc = self._video_to_document(video_id, snippet)
                    documents.append(doc)

                    # Optionally fetch top comments
                    try:
                        comments = await self._fetch_comments(video_id, max_comments=5)
                        documents.extend(comments)
                    except Exception as e:
                        self.logger.warning(f"Could not fetch comments for {video_id}: {e}")

                self.logger.info(f"Fetched {len(documents)} documents for query: {query}")

            except HttpError as e:
                self.logger.error(f"YouTube API error for query '{query}': {e}")
                continue
            except Exception as e:
                self.logger.error(f"Error searching YouTube for '{query}': {e}")
                continue

        self.logger.info(f"Total documents ingested from YouTube: {len(documents)}")
        return documents

    def _video_to_document(self, video_id: str, snippet: Dict[str, Any]) -> Document:
        """Convert YouTube video to Document."""
        published_str = snippet.get("publishedAt", "")
        published_at = None
        if published_str:
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except Exception:
                pass

        return Document(
            external_id=f"youtube_video_{video_id}",
            url=f"https://www.youtube.com/watch?v={video_id}",
            author_handle=snippet.get("channelTitle"),
            title=snippet.get("title"),
            body=snippet.get("description", ""),
            published_at=published_at,
            raw_json={
                "video_id": video_id,
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "thumbnails": snippet.get("thumbnails", {}),
            },
        )

    async def _fetch_comments(self, video_id: str, max_comments: int = 5) -> List[Document]:
        """Fetch top comments for a video.

        Args:
            video_id: YouTube video ID
            max_comments: Maximum comments to fetch

        Returns:
            List of comment documents
        """
        if not self.youtube:
            return []

        try:
            comments_response = self.youtube.commentThreads().list(
                videoId=video_id,
                part="snippet",
                maxResults=max_comments,
                order="relevance",
            ).execute()

            documents = []
            for item in comments_response.get("items", []):
                comment = item["snippet"]["topLevelComment"]["snippet"]

                published_str = comment.get("publishedAt", "")
                published_at = None
                if published_str:
                    try:
                        published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
                    except Exception:
                        pass

                doc = Document(
                    external_id=f"youtube_comment_{item['id']}",
                    url=f"https://www.youtube.com/watch?v={video_id}&lc={item['id']}",
                    author_handle=comment.get("authorDisplayName"),
                    title=f"Comment on video {video_id}",
                    body=comment.get("textDisplay", ""),
                    published_at=published_at,
                    raw_json={
                        "video_id": video_id,
                        "comment_id": item["id"],
                        "like_count": comment.get("likeCount", 0),
                    },
                )
                documents.append(doc)

            return documents

        except Exception as e:
            self.logger.warning(f"Error fetching comments for video {video_id}: {e}")
            return []
