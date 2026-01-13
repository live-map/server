"""
Integration tests for Pipeline V2 (Social Media Verification).

Run with: uv run pytest tests/test_pipeline_v2.py -v
Requires: Database running (docker compose up -d db)
"""

import asyncio
import pytest

from app.services.verification.stage0_preprocessing import run_stage0, Stage0Result
from app.services.verification.stage1.channel_credibility import (
    calculate_channel_credibility,
    calculate_text_length_threshold,
    ChannelCredibilityResult,
)
from app.services.verification.stage1.pipeline import (
    calculate_stage1_score_v2,
    Stage1ResultV2,
)


class TestStage0Preprocessing:
    """Test Stage 0 text preprocessing."""

    def test_normalize_hashtags(self):
        """Hashtags should be extracted and normalized."""
        result = run_stage0("#Ukraine #War news update", platform="TELEGRAM")
        assert result.completed
        assert "Ukraine" in result.hashtags
        assert "War" in result.hashtags
        assert "#" not in result.normalized_text

    def test_detect_telegram_forward(self):
        """Should detect Telegram forwards."""
        text = "Forwarded from Military Intel\nBig news here!"
        result = run_stage0(text, platform="TELEGRAM")
        assert result.is_repost
        assert result.repost_type == "FORWARD"
        assert result.original_source == "Military Intel"

    def test_detect_retweet(self):
        """Should detect X/Twitter retweets."""
        text = "RT @warmonitor: Breaking news about conflict"
        result = run_stage0(text, platform="X")
        assert result.is_repost
        assert result.repost_type in ["RETWEET", "FORWARD"]

    def test_extract_coordinates_decimal(self):
        """Should extract decimal coordinates."""
        text = "Strike at coordinates 48.5953, 37.9934"
        result = run_stage0(text)
        assert result.has_coordinates
        assert result.primary_latitude is not None
        assert abs(result.primary_latitude - 48.5953) < 0.01

    def test_extract_coordinates_latlong(self):
        """Should extract lat/lng format."""
        text = "Location: lat: 50.45, lng: 30.52"
        result = run_stage0(text)
        assert result.has_coordinates

    def test_military_terminology(self):
        """Should detect military terminology."""
        text = "BTG destroyed, 3x T-72 tanks and HIMARS strike confirmed"
        result = run_stage0(text)
        assert result.has_military_content

    def test_too_short_text(self):
        """Should flag too short text."""
        result = run_stage0("Hi", min_text_length=20)
        assert result.is_too_short

    def test_mostly_hashtags(self):
        """Should flag text that is mostly hashtags."""
        result = run_stage0("#tag1 #tag2 #tag3 #tag4 #tag5")
        assert result.is_mostly_hashtags


class TestChannelCredibility:
    """Test channel credibility calculation."""

    def test_tier1_channel(self):
        """Large verified channel should be tier 1."""
        result = calculate_channel_credibility(
            subscriber_count=150000,
            channel_age_days=800,
            is_verified=True,
            historical_accuracy=0.9,
        )
        assert result.tier == 1
        assert result.score >= 0.8

    def test_unknown_channel(self):
        """Unknown channel should be tier 5."""
        result = calculate_channel_credibility()
        assert result.tier == 5
        assert result.score < 0.3

    def test_blocked_channel(self):
        """Blocked channel should have score 0."""
        result = calculate_channel_credibility(
            subscriber_count=100000,
            is_blocked=True,
        )
        assert result.score == 0.0
        assert result.is_blocked

    def test_trusted_override(self):
        """Manually trusted channel should have high score."""
        result = calculate_channel_credibility(
            subscriber_count=100,
            is_trusted=True,
        )
        assert result.score >= 0.8
        assert result.tier <= 2


class TestStage1V2Scoring:
    """Test Stage 1 v2 score calculation."""

    def test_best_case_score(self):
        """Best case should be 1.0."""
        score, breakdown = calculate_stage1_score_v2(
            channel_score=0.9,
            has_location=True,
            is_duplicate=False,
            has_coordinates=True,
        )
        assert score == 1.0
        assert "channel" in breakdown
        assert "location" in breakdown

    def test_no_location_still_continues(self):
        """No location should NOT block (v2 change)."""
        score, breakdown = calculate_stage1_score_v2(
            channel_score=0.5,
            has_location=False,
            is_duplicate=False,
            has_coordinates=False,
        )
        # Should still be above threshold
        assert score >= 0.3
        assert breakdown["location"] == 0.0

    def test_duplicate_blocked(self):
        """Duplicates should still be blocked."""
        score, breakdown = calculate_stage1_score_v2(
            channel_score=0.9,
            has_location=True,
            is_duplicate=True,
            has_coordinates=True,
        )
        assert score == 0.0
        assert "duplicate" in breakdown


class TestDuplicateThresholds:
    """Test dynamic duplicate thresholds."""

    def test_short_text_threshold(self):
        """Short text should have higher threshold."""
        threshold = calculate_text_length_threshold(50)
        assert threshold == 0.95

    def test_medium_text_threshold(self):
        """Medium text should have medium threshold."""
        threshold = calculate_text_length_threshold(200)
        assert threshold == 0.90

    def test_long_text_threshold(self):
        """Long text should have lower threshold."""
        threshold = calculate_text_length_threshold(500)
        assert threshold == 0.85


# Integration test (requires DB)
@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires database connection")
async def test_full_pipeline_v2():
    """Test full pipeline v2 execution."""
    from app.services.verification import run_pipeline_v2

    result = await run_pipeline_v2(
        text="HIMARS strike near Bakhmut reported by multiple sources",
        channel_info={
            "subscriber_count": 50000,
            "channel_age_days": 400,
            "is_verified": False,
        },
        platform="TELEGRAM",
        skip_stage3=True,  # Skip LLM for test
    )

    assert result.stage0_completed
    assert result.stage1_completed
    # Location is now optional - should NOT be skipped
    assert result.skipped_at_stage != 1 or "location" not in (result.skip_reason or "").lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
