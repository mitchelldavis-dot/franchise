"""Entity extraction for leads."""

import re
from typing import Dict, Any, Optional, List
from datetime import datetime

import dateparser
from loguru import logger

from ..config import get_config


class EntityExtractor:
    """Extract entities from text without doxxing."""

    def __init__(self):
        """Initialize entity extractor."""
        self.config = get_config()
        self.florida_cities = self.config.get_florida_config().get("florida_cities", [])
        self.florida_counties = self.config.get_florida_config().get("florida_counties", [])

    def extract_location(self, text: str) -> Dict[str, Any]:
        """Extract location information.

        Returns:
            Dict with location_text, city, state, geo_confidence, geo_why, is_florida
        """
        result = {
            "location_text": None,
            "location_city": None,
            "location_state": None,
            "geo_confidence": "low",
            "geo_why": None,
            "is_florida": False,
        }

        text_lower = text.lower()

        # Pattern 1: Explicit city, state format
        city_state_pattern = r'\b([A-Z][a-zA-Z\s]+),\s*(FL|Florida)\b'
        matches = re.findall(city_state_pattern, text)
        if matches:
            city, state = matches[0]
            result["location_text"] = f"{city}, {state}"
            result["location_city"] = city.strip()
            result["location_state"] = "FL"
            result["geo_confidence"] = "high"
            result["geo_why"] = "Explicit city, state mention"
            result["is_florida"] = True
            return result

        # Pattern 2: "in [city]" or "near [city]"
        for city in self.florida_cities:
            patterns = [
                rf'\bin {re.escape(city.lower())}\b',
                rf'\bnear {re.escape(city.lower())}\b',
                rf'\b{re.escape(city.lower())} area\b',
                rf'\b{re.escape(city.lower())},',
            ]
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    result["location_text"] = f"{city}, FL"
                    result["location_city"] = city
                    result["location_state"] = "FL"
                    result["geo_confidence"] = "high" if "," in pattern else "medium"
                    result["geo_why"] = f"Found '{city}' with location context"
                    result["is_florida"] = True
                    return result

        # Pattern 3: Florida counties
        for county in self.florida_counties:
            if re.search(rf'\b{re.escape(county.lower())}\s+county\b', text_lower):
                result["location_text"] = f"{county} County, FL"
                result["location_state"] = "FL"
                result["geo_confidence"] = "medium"
                result["geo_why"] = f"Found '{county} County'"
                result["is_florida"] = True
                return result

        # Pattern 4: Just "Florida" or "FL"
        if re.search(r'\bflorida\b|\bfl\b', text_lower):
            result["location_text"] = "Florida"
            result["location_state"] = "FL"
            result["geo_confidence"] = "low"
            result["geo_why"] = "Generic Florida mention"
            result["is_florida"] = True
            return result

        return result

    def extract_budget_hints(self, text: str) -> List[str]:
        """Extract budget/investment hints.

        Returns:
            List of budget hint strings
        """
        hints = []

        # Pattern 1: $XXXk format
        amount_pattern = r'\$\d{1,3}[kK]'
        matches = re.findall(amount_pattern, text)
        hints.extend(matches)

        # Pattern 2: "under $XXX,XXX" format
        under_pattern = r'under \$[\d,]+'
        matches = re.findall(under_pattern, text, re.IGNORECASE)
        hints.extend(matches)

        # Pattern 3: Specific amounts like "$200,000"
        specific_pattern = r'\$\d{1,3}(,\d{3})+'
        matches = re.findall(specific_pattern, text)
        hints.extend([''.join(m) if isinstance(m, tuple) else m for m in matches])

        # Pattern 4: Liquid capital mentions
        if re.search(r'liquid capital', text, re.IGNORECASE):
            hints.append("liquid capital mentioned")

        # Pattern 5: Net worth mentions
        if re.search(r'net worth', text, re.IGNORECASE):
            hints.append("net worth mentioned")

        return list(set(hints))  # Remove duplicates

    def extract_timeline_hints(self, text: str) -> List[str]:
        """Extract timeline/urgency hints.

        Returns:
            List of timeline hint strings
        """
        hints = []

        # Common timeline phrases
        timeline_patterns = [
            r'this year',
            r'next \d+ months',
            r'within \d+ months',
            r'by end of year',
            r'by \w+ \d{4}',
            r'asap',
            r'urgently',
            r'ready to start',
            r'ready to move forward',
            r'looking to start soon',
            r'immediate',
        ]

        for pattern in timeline_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            hints.extend(matches)

        # Try to parse specific dates
        date_patterns = [
            r'\b\d{1,2}/\d{1,2}/\d{2,4}\b',  # 12/31/2024
            r'\b\w+ \d{1,2},? \d{4}\b',  # January 1, 2024
        ]

        for pattern in date_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    parsed = dateparser.parse(match)
                    if parsed:
                        hints.append(f"Target date: {parsed.strftime('%Y-%m-%d')}")
                except Exception:
                    pass

        return list(set(hints))

    def extract_business_name(self, text: str) -> Optional[str]:
        """Extract potential business name if explicitly mentioned.

        Only extract if clearly stated, e.g., "my gym is called X" or "I own X Studio"
        """
        # Pattern: "my [business type] is called/named [name]"
        patterns = [
            r'my (?:gym|studio|business) is (?:called|named) ([A-Z][\w\s]+)',
            r'I own ([A-Z][\w\s]+(?:Gym|Studio|Fitness|Training))',
            r'we own ([A-Z][\w\s]+(?:Gym|Studio|Fitness|Training))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None

    def extract_handle(self, author_handle: Optional[str], url: Optional[str]) -> Optional[str]:
        """Extract and normalize handle/username.

        Args:
            author_handle: Author handle from source
            url: URL if available

        Returns:
            Normalized handle
        """
        if author_handle:
            # Clean up handle
            handle = author_handle.strip().lstrip('@').lstrip('u/')
            return handle

        # Try to extract from URL
        if url:
            # Reddit: /u/username or /user/username
            reddit_match = re.search(r'/u(?:ser)?/([^/]+)', url)
            if reddit_match:
                return reddit_match.group(1)

            # Twitter: twitter.com/username
            twitter_match = re.search(r'twitter\.com/([^/]+)', url)
            if twitter_match:
                return twitter_match.group(1)

        return None


def extract_entities(
    text: str,
    title: Optional[str] = None,
    author_handle: Optional[str] = None,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract all entities from text.

    Args:
        text: Main text content
        title: Optional title
        author_handle: Optional author handle
        url: Optional URL

    Returns:
        Dict with all extracted entities
    """
    extractor = EntityExtractor()

    full_text = f"{title or ''} {text}"

    entities = {
        "handle": extractor.extract_handle(author_handle, url),
        "location": extractor.extract_location(full_text),
        "budget_hints": extractor.extract_budget_hints(full_text),
        "timeline_hints": extractor.extract_timeline_hints(full_text),
        "business_name": extractor.extract_business_name(full_text),
    }

    return entities
