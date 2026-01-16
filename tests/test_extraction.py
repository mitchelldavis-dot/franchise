"""Tests for entity extraction."""

import pytest

from franchise_radar.extraction import extract_entities


def test_extract_florida_location_explicit():
    """Test extraction of explicit Florida location."""
    text = "I'm looking for opportunities in Miami, FL"

    entities = extract_entities(text)

    assert entities["location"]["location_city"] == "Miami"
    assert entities["location"]["location_state"] == "FL"
    assert entities["location"]["is_florida"] is True
    assert entities["location"]["geo_confidence"] == "high"


def test_extract_florida_location_city_only():
    """Test extraction with city name only."""
    text = "Looking for gyms in Orlando"

    entities = extract_entities(text)

    assert entities["location"]["location_city"] == "Orlando"
    assert entities["location"]["location_state"] == "FL"
    assert entities["location"]["is_florida"] is True
    assert entities["location"]["geo_confidence"] in ["high", "medium"]


def test_extract_budget_hints():
    """Test extraction of budget signals."""
    text = """
    I have $250k liquid capital and net worth of $500k. Looking at franchises
    under $300k.
    """

    entities = extract_entities(text)

    assert len(entities["budget_hints"]) > 0
    assert any("250k" in hint or "300k" in hint for hint in entities["budget_hints"])


def test_extract_timeline_hints():
    """Test extraction of timeline signals."""
    text = "Looking to start within 6 months, ready to move forward this year"

    entities = extract_entities(text)

    assert len(entities["timeline_hints"]) > 0


def test_extract_handle_from_reddit():
    """Test handle extraction from Reddit-style URL."""
    text = "Test content"
    url = "https://reddit.com/u/fitness_entrepreneur"

    entities = extract_entities(text, url=url)

    assert entities["handle"] == "fitness_entrepreneur"


def test_extract_business_name():
    """Test business name extraction."""
    text = "I own Peak Performance Gym and we're struggling"

    entities = extract_entities(text)

    assert entities["business_name"] == "Peak Performance Gym"


def test_no_location_found():
    """Test when no location is found."""
    text = "Looking for franchise opportunities"

    entities = extract_entities(text)

    assert entities["location"]["is_florida"] is False
    assert entities["location"]["location_city"] is None
