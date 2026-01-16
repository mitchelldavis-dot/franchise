"""Tests for scoring engine."""

import pytest
from datetime import datetime, timedelta

from franchise_radar.scoring import score_franchise_buyer, score_owner_pain


def test_score_franchise_buyer_high_intent():
    """Test scoring for high-intent franchise buyer."""
    text = """
    I'm looking to buy a gym franchise in Miami, FL. My budget is around $250k
    and I'm ready to start within the next 6 months. I've reviewed the FDD and
    Item 19 looks promising. Any recommendations?
    """

    result = score_franchise_buyer(text, title="Looking for franchise opportunities")

    assert result.score > 60, "Should score high for strong buyer intent"
    assert "franchise" in result.reasons[0].lower() or "buyer" in str(result.reasons)
    assert result.tier in ["Ready", "Comparing"]
    assert len(result.extracted_fields) > 0


def test_score_franchise_buyer_no_fitness_context():
    """Test that non-fitness franchise content scores low."""
    text = """
    I want to buy an NFL franchise. Looking at sports franchises in general.
    What's the best NFL team to invest in?
    """

    result = score_franchise_buyer(text)

    assert result.score < 40, "Should score low for non-fitness franchise"
    assert "QUALIFICATION FAILED" in " ".join(result.reasons)


def test_score_owner_pain_high_intent():
    """Test scoring for gym owner with pain signals."""
    text = """
    My yoga studio in Tampa is really struggling. We can't get leads and our
    Facebook ads stopped working. Member churn is killing us - down from 120
    to 80 members in 6 months. Need help urgently!
    """

    result = score_owner_pain(text, title="Need marketing help")

    assert result.score > 60, "Should score high for owner pain"
    assert result.tier in ["Urgent", "Serious Pain"]
    assert len(result.reasons) > 0


def test_score_owner_pain_no_ownership():
    """Test that consumer complaints don't score as owner pain."""
    text = """
    I'm a member at a gym and it's terrible. The staff is rude and equipment
    is broken. Looking for a new gym in my area.
    """

    result = score_owner_pain(text)

    assert result.score < 40, "Should score low without ownership signals"
    assert "QUALIFICATION FAILED" in " ".join(result.reasons)


def test_proximity_bonus():
    """Test that proximity of related terms increases score."""
    text1 = "I want to buy a gym franchise"
    text2 = "I want to buy a franchise. Also, I like gym equipment."

    result1 = score_franchise_buyer(text1)
    result2 = score_franchise_buyer(text2)

    # Text1 should score higher due to proximity
    assert result1.score > result2.score


def test_freshness_boost():
    """Test that recent content gets freshness boost."""
    text = "Looking for franchise opportunities in fitness industry"

    recent = datetime.utcnow() - timedelta(hours=1)
    old = datetime.utcnow() - timedelta(days=60)

    result_recent = score_franchise_buyer(text, published_at=recent)
    result_old = score_franchise_buyer(text, published_at=old)

    assert result_recent.score > result_old.score


def test_negative_phrases_penalty():
    """Test that negative/exclusion phrases reduce score."""
    text = """
    Looking for a job at a gym franchise. Hiring franchise mode coordinator.
    This is a career opportunity for franchise sales.
    """

    result = score_franchise_buyer(text)

    assert result.score < 50, "Should be penalized for job-related content"
