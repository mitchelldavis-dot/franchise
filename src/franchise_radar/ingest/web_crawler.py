"""Web crawler with robots.txt compliance."""

import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from readability import Document as ReadabilityDocument
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

from .base import BaseAdapter, Document


class WebCrawler(BaseAdapter):
    """Compliant web crawler respecting robots.txt."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize web crawler.

        Args:
            config: Configuration dict
        """
        super().__init__("web_crawl", config)
        self.robots_cache: Dict[str, RobotFileParser] = {}
        self.visited_urls: Set[str] = set()
        self.crawl_delay = config.get("crawl_delay", 1.0)
        self.max_pages_per_domain = config.get("max_pages_per_domain", 500)

    def validate_config(self) -> bool:
        """Validate crawler configuration."""
        return True  # Web crawler can work without specific config

    async def ingest(
        self,
        since: Optional[datetime] = None,
        limit: Optional[int] = None,
    ) -> List[Document]:
        """Crawl web pages from seed URLs.

        Args:
            since: Not used for web crawler
            limit: Max pages to crawl total

        Returns:
            List of documents
        """
        seed_urls = self.config.get("seed_urls", [])
        if not seed_urls:
            self.logger.warning("No seed URLs provided for web crawler")
            return []

        documents = []
        domain_counts: Dict[str, int] = {}

        for seed_url in seed_urls:
            if limit and len(documents) >= limit:
                break

            domain = urlparse(seed_url).netloc
            if domain not in domain_counts:
                domain_counts[domain] = 0

            # Check if we've hit domain limit
            if domain_counts[domain] >= self.max_pages_per_domain:
                self.logger.warning(f"Hit max pages limit for {domain}")
                continue

            try:
                # Crawl this URL and discover links
                crawled = await self._crawl_page(seed_url)
                if crawled:
                    documents.append(crawled)
                    domain_counts[domain] += 1

                # Respect crawl delay
                await asyncio.sleep(self.crawl_delay)

            except Exception as e:
                self.logger.error(f"Error crawling {seed_url}: {e}")
                continue

        self.logger.info(f"Total documents crawled: {len(documents)}")
        return documents

    async def _crawl_page(self, url: str) -> Optional[Document]:
        """Crawl a single page.

        Args:
            url: URL to crawl

        Returns:
            Document if successful, None otherwise
        """
        # Check if already visited
        if url in self.visited_urls:
            return None

        # Check robots.txt
        if not await self._can_fetch(url):
            self.logger.warning(f"robots.txt disallows crawling: {url}")
            return None

        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": "FranchiseRadar/0.1.0 (Educational/Research)"}
                )
                response.raise_for_status()

                # Mark as visited
                self.visited_urls.add(url)

                # Parse HTML
                soup = BeautifulSoup(response.content, "html.parser")

                # Extract readable content using readability
                doc = ReadabilityDocument(response.content)
                title = doc.title()
                body_html = doc.summary()

                # Clean up body text
                body_soup = BeautifulSoup(body_html, "html.parser")
                body_text = body_soup.get_text(separator=" ", strip=True)

                # Create document
                return Document(
                    external_id=f"web_{url}",
                    url=url,
                    author_handle=None,
                    title=title,
                    body=body_text,
                    published_at=None,
                    raw_json={
                        "domain": urlparse(url).netloc,
                        "status_code": response.status_code,
                    },
                )

        except Exception as e:
            self.logger.error(f"Error crawling {url}: {e}")
            return None

    async def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if allowed to fetch
        """
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        # Check cache
        if domain not in self.robots_cache:
            # Fetch and parse robots.txt
            rp = RobotFileParser()
            rp.set_url(robots_url)
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(robots_url)
                    if response.status_code == 200:
                        rp.parse(response.text.splitlines())
                    else:
                        # No robots.txt, allow crawling
                        rp.allow_all = True
            except Exception as e:
                self.logger.warning(f"Could not fetch robots.txt for {domain}: {e}")
                # If can't fetch robots.txt, be conservative and disallow
                rp.allow_all = False

            self.robots_cache[domain] = rp

        rp = self.robots_cache[domain]
        user_agent = "FranchiseRadar"

        return rp.can_fetch(user_agent, url)
