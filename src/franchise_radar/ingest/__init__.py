"""Ingestion adapters for various sources."""

from .reddit_adapter import RedditAdapter
from .rss_adapter import RSSAdapter
from .web_crawler import WebCrawler
from .youtube_adapter import YouTubeAdapter

__all__ = ["RedditAdapter", "RSSAdapter", "WebCrawler", "YouTubeAdapter"]
