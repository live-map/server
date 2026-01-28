"""
Tests for the Pipeline Metrics System (P2).
"""

import pytest
from datetime import datetime, timedelta

from app.agent.metrics import (
    PipelineMetrics,
    FilterStageStats,
    ScanCycleResult,
    SourceQualityMetrics,
    get_global_metrics,
    reset_global_metrics,
)


class TestFilterStageStats:
    """Test filter stage statistics."""

    def test_pass_rate_calculation(self):
        """Pass rate should be calculated correctly."""
        stats = FilterStageStats(total_input=100, passed=80, rejected=20)
        assert stats.pass_rate == 80.0

    def test_reject_rate_calculation(self):
        """Reject rate should be calculated correctly."""
        stats = FilterStageStats(total_input=100, passed=80, rejected=20)
        assert stats.reject_rate == 20.0

    def test_zero_input_returns_zero_rates(self):
        """Zero input should return zero rates."""
        stats = FilterStageStats(total_input=0, passed=0, rejected=0)
        assert stats.pass_rate == 0.0
        assert stats.reject_rate == 0.0


class TestSourceQualityMetrics:
    """Test source quality metrics."""

    def test_quality_score_calculation(self):
        """Quality score should be calculated correctly."""
        metrics = SourceQualityMetrics(
            total_events=100,
            passed_filters=80,
            published=50,
            avg_confidence=0.7,
            avg_importance=0.6,
        )
        # publish_rate=0.5, filter_rate=0.8
        # 0.5*0.4 + 0.8*0.3 + 0.7*0.15 + 0.6*0.15 = 0.2 + 0.24 + 0.105 + 0.09 = 0.635
        assert 0.63 <= metrics.quality_score <= 0.64

    def test_zero_events_returns_zero_quality(self):
        """Zero events should return zero quality score."""
        metrics = SourceQualityMetrics(total_events=0)
        assert metrics.quality_score == 0.0


class TestPipelineMetrics:
    """Test pipeline metrics collection."""

    def test_record_scan_cycle(self):
        """Should record scan cycle correctly."""
        metrics = PipelineMetrics()

        filter_stats = {
            "initial": 100,
            "recency_rejected": 10,
            "content_date_rejected": 5,
            "importance_rejected": 15,
            "confidence_passed": 50,
            "gate0_rejected": 5,
            "gate1_rejected": 5,
            "gate2_rejected": 5,
            "final_published": 35,
        }

        published_events = [
            {
                "category": "war",
                "sources": ["reuters.com"],
                "trigger_source": "gdelt",
                "confidence_score": 0.85,
                "importance_score": 0.75,
            },
            {
                "category": "protest",
                "sources": ["bbc.com"],
                "trigger_source": "gdelt",
                "confidence_score": 0.7,
                "importance_score": 0.6,
            },
        ]

        metrics.record_scan_cycle(filter_stats, published_events, 5.5)

        # Check timing
        timing = metrics.get_timing_report()
        assert timing["total_scans"] == 1
        assert timing["avg_duration_seconds"] == 5.5

        # Check categories
        categories = metrics.get_category_report()
        assert categories["war"] == 1
        assert categories["protest"] == 1

    def test_multiple_scan_cycles(self):
        """Should aggregate multiple scan cycles."""
        metrics = PipelineMetrics()

        for i in range(3):
            filter_stats = {"initial": 50, "final_published": 10}
            published = [{"category": "war", "trigger_source": "gdelt"}]
            metrics.record_scan_cycle(filter_stats, published, 2.0)

        timing = metrics.get_timing_report()
        assert timing["total_scans"] == 3
        assert timing["avg_duration_seconds"] == 2.0
        assert timing["total_processing_time"] == 6.0

    def test_get_full_report(self):
        """Should return full metrics report."""
        metrics = PipelineMetrics()

        filter_stats = {"initial": 100, "final_published": 10}
        published = [{"category": "war", "trigger_source": "gdelt"}]
        metrics.record_scan_cycle(filter_stats, published, 3.0)

        report = metrics.get_report()

        assert "generated_at" in report
        assert "timing" in report
        assert "filters" in report
        assert "sources" in report
        assert "categories" in report
        assert "recent_scans" in report

    def test_recent_history(self):
        """Should return recent scan history."""
        metrics = PipelineMetrics()

        for i in range(5):
            filter_stats = {"initial": 10 * (i + 1), "final_published": i + 1}
            published = [{"category": "war"}]
            metrics.record_scan_cycle(filter_stats, published, 1.0)

        history = metrics.get_recent_history(3)

        assert len(history) == 3
        # Most recent first
        assert history[0]["initial_events"] == 50
        assert history[2]["initial_events"] == 30

    def test_reset(self):
        """Should reset all metrics."""
        metrics = PipelineMetrics()

        filter_stats = {"initial": 100, "final_published": 10}
        published = [{"category": "war"}]
        metrics.record_scan_cycle(filter_stats, published, 3.0)

        metrics.reset()

        timing = metrics.get_timing_report()
        assert timing["total_scans"] == 0


class TestGlobalMetrics:
    """Test global metrics singleton."""

    def test_get_global_metrics(self):
        """Should return same instance."""
        reset_global_metrics()
        m1 = get_global_metrics()
        m2 = get_global_metrics()
        assert m1 is m2

    def test_reset_global_metrics(self):
        """Should reset global instance."""
        metrics = get_global_metrics()
        filter_stats = {"initial": 100, "final_published": 10}
        metrics.record_scan_cycle(filter_stats, [], 1.0)

        reset_global_metrics()

        # Should still work after reset
        metrics = get_global_metrics()
        timing = metrics.get_timing_report()
        assert timing["total_scans"] == 0
