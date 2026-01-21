"""
Event Clusterer for grouping related events.

Uses DBSCAN clustering on event embeddings to identify clusters of related events.
This enables story tracking by grouping events about the same ongoing story.

Features:
- DBSCAN clustering with cosine distance
- Configurable epsilon (max distance) and min_samples
- Database integration for fetching and updating cluster assignments
- Cluster metadata (centroid, member count, time range)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import agent_settings

if TYPE_CHECKING:
    from app.models.event import Event

logger = logging.getLogger(__name__)


@dataclass
class ClusterInfo:
    """Information about an event cluster."""

    cluster_id: int
    event_ids: list[int] = field(default_factory=list)
    event_count: int = 0
    earliest_event: datetime | None = None
    latest_event: datetime | None = None
    representative_title: str = ""

    @property
    def time_span_hours(self) -> float | None:
        """Time span of the cluster in hours."""
        if self.earliest_event and self.latest_event:
            delta = self.latest_event - self.earliest_event
            return delta.total_seconds() / 3600
        return None


class EventClusterer:
    """
    Cluster related events using DBSCAN on embeddings.

    DBSCAN parameters:
    - eps: Maximum distance between samples (1 - similarity)
    - min_samples: Minimum samples to form a cluster

    Usage:
        clusterer = EventClusterer(db_session)
        clusters = await clusterer.cluster_events(category="war")
        await clusterer.update_cluster_assignments(clusters)
    """

    def __init__(
        self,
        db: AsyncSession,
        eps: float = 0.30,  # Max distance (1 - 0.70 = 0.30 for 70% similarity)
        min_samples: int = 2,  # Minimum events to form a cluster
        time_window_days: int | None = None,
    ):
        """
        Initialize event clusterer.

        Args:
            db: Database session
            eps: Maximum distance for DBSCAN (1 - min_similarity)
            min_samples: Minimum events to form a cluster
            time_window_days: Only cluster events within this time window
        """
        self.db = db
        self.eps = eps
        self.min_samples = min_samples
        self.time_window_days = time_window_days or agent_settings.dedup_time_window_days

        logger.debug(
            f"EventClusterer initialized: eps={self.eps}, "
            f"min_samples={self.min_samples}, time_window={self.time_window_days}d"
        )

    async def cluster_events(
        self,
        category: str | None = None,
        force_recluster: bool = False,
    ) -> dict[int, ClusterInfo]:
        """
        Cluster events using DBSCAN.

        Args:
            category: Filter events by category (optional)
            force_recluster: Re-cluster even if already assigned

        Returns:
            Dictionary mapping cluster_id to ClusterInfo
        """
        # Fetch events with embeddings
        events = await self._fetch_events(category, force_recluster)

        if len(events) < self.min_samples:
            logger.info(f"Not enough events for clustering: {len(events)} < {self.min_samples}")
            return {}

        # Extract embeddings as numpy array
        event_ids = [e.id for e in events]
        embeddings = np.array([e.embedding for e in events])

        logger.info(f"Clustering {len(events)} events with DBSCAN (eps={self.eps})")

        # Compute cosine distance matrix
        distance_matrix = cosine_distances(embeddings)

        # Run DBSCAN
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="precomputed",
        )
        labels = clustering.fit_predict(distance_matrix)

        # Build cluster info
        clusters: dict[int, ClusterInfo] = {}
        noise_count = 0

        for event, label in zip(events, labels):
            if label == -1:
                # Noise point (not in any cluster)
                noise_count += 1
                continue

            if label not in clusters:
                clusters[label] = ClusterInfo(
                    cluster_id=label,
                    event_ids=[],
                    event_count=0,
                )

            cluster = clusters[label]
            cluster.event_ids.append(event.id)
            cluster.event_count += 1

            # Update time range
            if event.created_at:
                if cluster.earliest_event is None or event.created_at < cluster.earliest_event:
                    cluster.earliest_event = event.created_at
                if cluster.latest_event is None or event.created_at > cluster.latest_event:
                    cluster.latest_event = event.created_at

            # Use first event's title as representative
            if not cluster.representative_title:
                cluster.representative_title = event.canonical_title or ""

        logger.info(
            f"Clustering complete: {len(clusters)} clusters, "
            f"{noise_count} noise events, {len(events)} total"
        )

        # Log cluster details
        for cluster_id, info in clusters.items():
            logger.debug(
                f"Cluster {cluster_id}: {info.event_count} events, "
                f"span={info.time_span_hours:.1f}h, title={info.representative_title[:50]}..."
            )

        return clusters

    async def update_cluster_assignments(
        self,
        clusters: dict[int, ClusterInfo],
    ) -> int:
        """
        Update cluster_id field for events in the database.

        Args:
            clusters: Dictionary of cluster information

        Returns:
            Number of events updated
        """
        from app.models.event import Event

        total_updated = 0

        for cluster_id, info in clusters.items():
            if not info.event_ids:
                continue

            # Update events with cluster_id
            result = await self.db.execute(
                update(Event)
                .where(Event.id.in_(info.event_ids))
                .values(cluster_id=cluster_id)
            )
            total_updated += result.rowcount

        await self.db.commit()

        logger.info(f"Updated cluster assignments for {total_updated} events")
        return total_updated

    async def get_cluster_events(
        self,
        cluster_id: int,
    ) -> list["Event"]:
        """
        Get all events in a cluster.

        Args:
            cluster_id: Cluster ID to query

        Returns:
            List of Event objects in the cluster
        """
        from app.models.event import Event

        result = await self.db.execute(
            select(Event)
            .where(Event.cluster_id == cluster_id)
            .order_by(Event.created_at.desc())
        )
        return list(result.scalars().all())

    async def _fetch_events(
        self,
        category: str | None = None,
        include_clustered: bool = False,
    ) -> list["Event"]:
        """
        Fetch events for clustering.

        Args:
            category: Filter by category
            include_clustered: Include events already assigned to clusters

        Returns:
            List of Event objects with embeddings
        """
        from app.models.event import Event

        # Time window filter
        cutoff_date = datetime.utcnow() - timedelta(days=self.time_window_days)

        # Build query
        query = select(Event).where(
            Event.is_active == True,
            Event.embedding.isnot(None),
            Event.created_at >= cutoff_date,
        )

        if category:
            query = query.where(Event.category == category)

        if not include_clustered:
            query = query.where(Event.cluster_id.is_(None))

        query = query.order_by(Event.created_at.desc())

        result = await self.db.execute(query)
        return list(result.scalars().all())


async def cluster_and_update_events(
    db: AsyncSession,
    category: str | None = None,
) -> dict[int, ClusterInfo]:
    """
    Convenience function to cluster events and update database.

    Args:
        db: Database session
        category: Filter by category (optional)

    Returns:
        Dictionary of cluster information
    """
    clusterer = EventClusterer(db)
    clusters = await clusterer.cluster_events(category)

    if clusters:
        await clusterer.update_cluster_assignments(clusters)

    return clusters
