"""Reddit ingestion adapter using PRAW."""

import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import praw
from praw.models import Submission, Comment
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from .base import BaseAdapter, Document


class RedditAdapter(BaseAdapter):
    """Adapter for Reddit using official API (PRAW)."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Reddit adapter.

        Args:
            config: Configuration dict
        """
        super().__init__("reddit", config)
        self.reddit: Optional[praw.Reddit] = None
        self._init_reddit()

    def _init_reddit(self):
        """Initialize Reddit API client."""
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "FranchiseRadar/0.1.0")

        if not client_id or not client_secret:
            self.logger.warning("Reddit credentials not found. Reddit ingestion disabled.")
            return

        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
            )
            self.logger.info("Reddit API initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Reddit API: {e}")
            self.reddit = None

    def validate_config(self) -> bool:
        """Validate Reddit configuration."""
        if not self.reddit:
            return False

        subreddits = self.config.get("subreddits", [])
        if not subreddits:
            self.logger.warning("No subreddits configured")
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
        """Ingest posts and comments from configured subreddits.

        Args:
            since: Only fetch posts after this time (default: 24h ago)
            limit: Max posts per subreddit (default: 100)

        Returns:
            List of documents
        """
        if not self.reddit:
            self.logger.warning("Reddit API not initialized")
            return []

        if since is None:
            since = datetime.utcnow() - timedelta(hours=24)

        if limit is None:
            limit = 100

        subreddits = self.config.get("subreddits", [])
        documents = []

        for subreddit_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                self.logger.info(f"Ingesting from r/{subreddit_name}")

                # Fetch new posts
                for submission in subreddit.new(limit=limit):
                    created_time = datetime.utcfromtimestamp(submission.created_utc)

                    if created_time < since:
                        continue

                    # Create document for submission
                    doc = self._submission_to_document(submission)
                    documents.append(doc)

                    # Also ingest top comments
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments.list()[:10]:  # Top 10 comments
                        comment_time = datetime.utcfromtimestamp(comment.created_utc)
                        if comment_time >= since:
                            comment_doc = self._comment_to_document(comment, submission)
                            documents.append(comment_doc)

                self.logger.info(f"Fetched {len(documents)} documents from r/{subreddit_name}")

            except Exception as e:
                self.logger.error(f"Error ingesting r/{subreddit_name}: {e}")
                continue

        self.logger.info(f"Total documents ingested from Reddit: {len(documents)}")
        return documents

    def _submission_to_document(self, submission: Submission) -> Document:
        """Convert Reddit submission to Document."""
        return Document(
            external_id=f"reddit_post_{submission.id}",
            url=f"https://reddit.com{submission.permalink}",
            author_handle=str(submission.author) if submission.author else None,
            title=submission.title,
            body=submission.selftext or "",
            published_at=datetime.utcfromtimestamp(submission.created_utc),
            raw_json={
                "id": submission.id,
                "subreddit": str(submission.subreddit),
                "score": submission.score,
                "num_comments": submission.num_comments,
                "url": submission.url,
            },
        )

    def _comment_to_document(self, comment: Comment, submission: Submission) -> Document:
        """Convert Reddit comment to Document."""
        return Document(
            external_id=f"reddit_comment_{comment.id}",
            url=f"https://reddit.com{comment.permalink}",
            author_handle=str(comment.author) if comment.author else None,
            title=f"Comment on: {submission.title}",
            body=comment.body or "",
            published_at=datetime.utcfromtimestamp(comment.created_utc),
            raw_json={
                "id": comment.id,
                "submission_id": submission.id,
                "subreddit": str(submission.subreddit),
                "score": comment.score,
                "parent_id": comment.parent_id,
            },
        )
