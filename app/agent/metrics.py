"""
Metrics System for News Scanner Pipeline (P2)

Tracks and reports:
1. Pipeline filter statistics (per stage)
2. Source quality metrics
3. Processing time metrics
4. Category distribution
5. Accuracy metrics (when feedback available)

Usage:
    from app.agent.metrics import PipelineMetrics, get_global_metrics

    metrics = get_global_metrics()
    metrics.record_scan_cycle(filter_stats, published_events, duration_seconds)
    report = metrics.get_report()
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FilterStageStats:
    """Statistics for a single filter stage."""
    total_input: int = 0
    passed: int = 0
    rejected: int = 0

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate as percentage."""
        if self.total_input == 0:
            return 0.0
        return (self.passed / self.total_input) * 100

    @property
    def reject_rate(self) -> float:
        """Calculate reject rate as percentage."""
        if self.total_input == 0:
            return 0.0
        return (self.rejected / self.total_input) * 100


@dataclass
class ScanCycleResult:
    """Result of a single scan cycle."""
    timestamp: datetime
    duration_seconds: float
    initial_events: int
    published_events: int
    filter_stats: dict[str, int]
    categories: dict[str, int]
    sources: list[str]


@dataclass
class SourceQualityMetrics:
    """Quality metrics for a source."""
    total_events: int = 0
    passed_filters: int = 0
    published: int = 0
    avg_confidence: float = 0.0
    avg_importance: float = 0.0

    @property
    def quality_score(self) -> float:
        """Overall quality score (0-1)."""
        if self.total_events == 0:
            return 0.0

        publish_rate = self.published / self.total_events
        filter_rate = self.passed_filters / self.total_events

        # Weighted average
        return (
            publish_rate * 0.4 +
            filter_rate * 0.3 +
            self.avg_confidence * 0.15 +
            self.avg_importance * 0.15
        )


class PipelineMetrics:
    """
    Metrics collector for the news scanner pipeline.

    Tracks metrics across scan cycles and provides aggregated reports.
    """

    def __init__(self, retention_hours: int = 24):
        """
        Initialize metrics collector.

        Args:
            retention_hours: How long to retain detailed metrics
        """
        self.retention_hours = retention_hours
        self._scan_history: list[ScanCycleResult] = []

        # Aggregated stats
        self._filter_stats: dict[str, FilterStageStats] = defaultdict(FilterStageStats)
        self._source_metrics: dict[str, SourceQualityMetrics] = defaultdict(SourceQualityMetrics)
        self._category_counts: dict[str, int] = defaultdict(int)

        # Time tracking
        self._total_scans: int = 0
        self._total_processing_time: float = 0.0
        self._last_cleanup: datetime = datetime.utcnow()

    def record_scan_cycle(
        self,
        filter_stats: dict[str, int],
        published_events: list[dict],
        duration_seconds: float,
    ) -> None:
        """
        Record metrics from a scan cycle.

        Args:
            filter_stats: Filter statistics dict from scanner
            published_events: List of published event dicts
            duration_seconds: Total scan duration
        """
        timestamp = datetime.utcnow()
        self._total_scans += 1
        self._total_processing_time += duration_seconds

        # Extract category distribution
        categories = defaultdict(int)
        sources = []

        for event in published_events:
            category = event.get("category", "other")
            categories[category] += 1
            self._category_counts[category] += 1

            # Track sources
            event_sources = event.get("sources", [])
            sources.extend(event_sources)

            # Update source metrics
            trigger_source = event.get("trigger_source", "unknown")
            self._update_source_metrics(
                trigger_source,
                confidence=event.get("confidence_score", 0.5),
                importance=event.get("importance_score", 0.5),
                published=True,
            )

        # Record scan result
        result = ScanCycleResult(
            timestamp=timestamp,
            duration_seconds=duration_seconds,
            initial_events=filter_stats.get("initial", 0),
            published_events=len(published_events),
            filter_stats=dict(filter_stats),
            categories=dict(categories),
            sources=sources,
        )
        self._scan_history.append(result)

        # Update filter stage stats
        self._update_filter_stats(filter_stats)

        # Log summary
        logger.info(
            f"[METRICS] Scan #{self._total_scans}: "
            f"{result.initial_events} → {result.published_events} events "
            f"({duration_seconds:.1f}s)"
        )

        # Periodic cleanup
        self._maybe_cleanup()

    def _update_filter_stats(self, filter_stats: dict[str, int]) -> None:
        """Update aggregated filter statistics."""
        initial = filter_stats.get("initial", 0)

        # Track each filter stage
        stages = [
            ("recency", filter_stats.get("recency_rejected", 0)),
            ("content_date", filter_stats.get("content_date_rejected", 0)),
            ("importance", filter_stats.get("importance_rejected", 0)),
            ("confidence", initial - filter_stats.get("confidence_passed", 0)),
            ("gate0", filter_stats.get("gate0_rejected", 0)),
            ("gate1", filter_stats.get("gate1_rejected", 0)),
            ("gate2", filter_stats.get("gate2_rejected", 0)),
        ]

        remaining = initial
        for stage_name, rejected in stages:
            stats = self._filter_stats[stage_name]
            stats.total_input += remaining
            stats.rejected += rejected
            stats.passed += max(0, remaining - rejected)
            remaining = max(0, remaining - rejected)

    def _update_source_metrics(
        self,
        source: str,
        confidence: float,
        importance: float,
        published: bool,
    ) -> None:
        """Update source quality metrics."""
        metrics = self._source_metrics[source]
        metrics.total_events += 1
        if published:
            metrics.published += 1
            metrics.passed_filters += 1

        # Running average for confidence/importance
        n = metrics.total_events
        metrics.avg_confidence = (
            (metrics.avg_confidence * (n - 1) + confidence) / n
        )
        metrics.avg_importance = (
            (metrics.avg_importance * (n - 1) + importance) / n
        )

    def _maybe_cleanup(self) -> None:
        """Cleanup old metrics if needed."""
        now = datetime.utcnow()
        if (now - self._last_cleanup).total_seconds() < 3600:  # Every hour
            return

        cutoff = now - timedelta(hours=self.retention_hours)
        self._scan_history = [
            r for r in self._scan_history
            if r.timestamp > cutoff
        ]
        self._last_cleanup = now

    def get_filter_report(self) -> dict[str, dict]:
        """Get filter stage statistics report."""
        report = {}
        for stage_name, stats in self._filter_stats.items():
            report[stage_name] = {
                "total_input": stats.total_input,
                "passed": stats.passed,
                "rejected": stats.rejected,
                "pass_rate": round(stats.pass_rate, 1),
                "reject_rate": round(stats.reject_rate, 1),
            }
        return report

    def get_source_report(self) -> dict[str, dict]:
        """Get source quality metrics report."""
        report = {}
        for source, metrics in self._source_metrics.items():
            report[source] = {
                "total_events": metrics.total_events,
                "published": metrics.published,
                "avg_confidence": round(metrics.avg_confidence, 3),
                "avg_importance": round(metrics.avg_importance, 3),
                "quality_score": round(metrics.quality_score, 3),
            }
        return report

    def get_category_report(self) -> dict[str, int]:
        """Get category distribution report."""
        return dict(self._category_counts)

    def get_timing_report(self) -> dict[str, float]:
        """Get timing statistics report."""
        if self._total_scans == 0:
            return {
                "total_scans": 0,
                "avg_duration_seconds": 0.0,
                "total_processing_time": 0.0,
            }

        return {
            "total_scans": self._total_scans,
            "avg_duration_seconds": round(
                self._total_processing_time / self._total_scans, 2
            ),
            "total_processing_time": round(self._total_processing_time, 2),
        }

    def get_recent_history(self, limit: int = 10) -> list[dict]:
        """Get recent scan history."""
        recent = self._scan_history[-limit:]
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "duration_seconds": round(r.duration_seconds, 2),
                "initial_events": r.initial_events,
                "published_events": r.published_events,
                "categories": r.categories,
            }
            for r in reversed(recent)
        ]

    def get_report(self) -> dict[str, Any]:
        """Get full metrics report."""
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "timing": self.get_timing_report(),
            "filters": self.get_filter_report(),
            "sources": self.get_source_report(),
            "categories": self.get_category_report(),
            "recent_scans": self.get_recent_history(5),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._scan_history.clear()
        self._filter_stats.clear()
        self._source_metrics.clear()
        self._category_counts.clear()
        self._total_scans = 0
        self._total_processing_time = 0.0
        logger.info("[METRICS] All metrics reset")


# Global singleton
_global_metrics: PipelineMetrics | None = None


def get_global_metrics() -> PipelineMetrics:
    """Get or create global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = PipelineMetrics()
    return _global_metrics


def reset_global_metrics() -> None:
    """Reset global metrics instance."""
    global _global_metrics
    if _global_metrics is not None:
        _global_metrics.reset()


# P2: Removed AccuracyMetrics class - defined but never used
# Can be re-added when feedback system is implemented
