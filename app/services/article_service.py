"""
Article Service for managing events and bilingual articles.

Handles:
- Event deduplication (hash + semantic)
- Update detection
- Article storage (English + Korean)
- Story chain management
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.deduplication import EventMatcher, MatchResult, MatchType, UpdateDetector, UpdateCheckResult
from app.models.article import Article, ArticleStatus, UpdateType
from app.models.event import Event

if TYPE_CHECKING:
    from app.agent.article_generator import GeneratedArticle

logger = logging.getLogger(__name__)


class ArticleService:
    """
    Service for managing events and articles.

    Workflow:
    1. Check for duplicate event (hash + semantic)
    2. If match found, check if it's an update
    3. Store event and article to database

    Usage:
        async with AsyncSessionLocal() as db:
            service = ArticleService(db)

            # Check for duplicates
            result = await service.check_duplicate(
                event_text, embedding, category
            )

            if result.is_duplicate:
                print("Skipping duplicate")
                return

            # Save article
            event, article = await service.save_article(
                bilingual_article,
                verification_result,
                embedding,
                category,
            )
    """

    def __init__(
        self,
        db: AsyncSession,
        duplicate_threshold: float = 0.95,
        potential_threshold: float = 0.85,
        time_window_days: int = 7,
    ):
        self.db = db
        self.event_matcher = EventMatcher(
            db,
            duplicate_threshold=duplicate_threshold,
            potential_threshold=potential_threshold,
            time_window_days=time_window_days,
        )
        self.update_detector = UpdateDetector()

    async def check_duplicate(
        self,
        event_text: str,
        embedding: list[float] | None = None,
        category: str | None = None,
    ) -> MatchResult:
        """
        Check if event is a duplicate.

        Args:
            event_text: Event description text
            embedding: Pre-computed embedding
            category: Event category

        Returns:
            MatchResult with match type and details
        """
        return await self.event_matcher.find_match(
            event_text, embedding, category
        )

    async def check_update(
        self,
        existing_event: Event,
        new_text: str,
        new_claims: list[dict] | None = None,
    ) -> UpdateCheckResult:
        """
        Check if new information warrants an update article.

        Args:
            existing_event: Existing event from database
            new_text: New event text
            new_claims: Extracted claims from new text

        Returns:
            UpdateCheckResult with decision
        """
        new_facts = None
        if new_claims:
            new_facts = self.update_detector.extract_key_facts(new_claims)

        return await self.update_detector.check_for_update(
            existing_event, new_text, new_facts
        )

    async def save_article(
        self,
        article_en: dict[str, Any],
        article_ko: dict[str, Any],
        event_text: str,
        embedding: list[float] | None,
        category: str,
        claims: list[dict] | None = None,
        verification_result: dict[str, Any] | None = None,
        sources: list[str] | None = None,
        is_update: bool = False,
        update_type: str | None = None,
        update_reason: str | None = None,
        existing_event_id: int | None = None,
    ) -> tuple[Event, Article]:
        """
        Save event and bilingual article to database.

        Args:
            article_en: English article dict
            article_ko: Korean article dict
            event_text: Original event text
            embedding: Event embedding
            category: Event category
            claims: Extracted claims
            verification_result: Verification results
            sources: List of sources
            is_update: Whether this is an update to existing event
            update_type: Type of update
            update_reason: Reason for update
            existing_event_id: Event ID if this is an update

        Returns:
            Tuple of (Event, Article)
        """
        # Extract facts and entities from claims
        key_facts = []
        key_entities = {}
        if claims:
            key_facts = self.update_detector.extract_key_facts(claims)
            key_entities = self.update_detector.extract_key_entities(claims)

        # Generate hashes
        event_hash = self.event_matcher.generate_event_hash(event_text)
        fact_hash = self.event_matcher.generate_fact_hash(key_facts) if key_facts else event_hash

        now = datetime.utcnow()

        if is_update and existing_event_id:
            # Update existing event
            result = await self.db.execute(
                select(Event).where(Event.id == existing_event_id)
            )
            event = result.scalar_one_or_none()

            if event:
                event.last_updated_at = now
                event.article_count += 1
                event.key_facts = json.dumps(key_facts)
                event.key_entities = json.dumps(key_entities)
                event.fact_hash = fact_hash
                if embedding:
                    event.embedding = embedding
            else:
                # Event not found, create new
                is_update = False
                existing_event_id = None
        else:
            event = None

        if not event:
            # Create new event
            event = Event(
                event_hash=event_hash,
                canonical_title=article_en.get("headline", event_text[:200]),
                embedding=embedding,
                key_entities=json.dumps(key_entities) if key_entities else None,
                key_facts=json.dumps(key_facts) if key_facts else None,
                fact_hash=fact_hash,
                category=category,
                first_reported_at=now,
                last_updated_at=now,
                article_count=1,
                is_active=True,
            )
            self.db.add(event)
            await self.db.flush()  # Get event ID

        # Create article
        verification = verification_result or {}
        article = Article(
            event_id=event.id,
            is_update=is_update,
            update_type=update_type,
            update_reason=update_reason,
            # English content
            headline_en=article_en.get("headline", ""),
            lead_en=article_en.get("lead", ""),
            nut_graph_en=article_en.get("nut_graph"),
            body_en=article_en.get("body", ""),
            full_text_en=article_en.get("full_text", ""),
            # Korean content
            headline_ko=article_ko.get("headline", ""),
            lead_ko=article_ko.get("lead", ""),
            nut_graph_ko=article_ko.get("nut_graph"),
            body_ko=article_ko.get("body", ""),
            full_text_ko=article_ko.get("full_text", ""),
            # Verification metadata
            claims_total=verification.get("total_claims", 0),
            claims_verified=verification.get("supported_count", 0),
            claims_refuted=verification.get("refuted_count", 0),
            claims_unverifiable=verification.get("nei_count", 0),
            verification_score=verification.get("overall_reliability", 0.0),
            # Sources
            source_count=len(sources) if sources else 0,
            sources_json=json.dumps(sources) if sources else None,
            # Status
            status=ArticleStatus.PUBLISHED.value,
            is_ai_generated=True,
            is_human_reviewed=False,
            published_at=now,
        )
        self.db.add(article)
        await self.db.commit()

        logger.info(
            f"Saved article: event_id={event.id}, article_id={article.id}, "
            f"is_update={is_update}, category={category}"
        )

        return event, article

    async def get_recent_events(
        self,
        category: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        """Get recent events, optionally filtered by category."""
        query = select(Event).where(Event.is_active == True)

        if category:
            query = query.where(Event.category == category)

        query = query.order_by(Event.last_updated_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_event_articles(self, event_id: int) -> list[Article]:
        """Get all articles for an event."""
        result = await self.db.execute(
            select(Article)
            .where(Article.event_id == event_id)
            .order_by(Article.published_at.desc())
        )
        return list(result.scalars().all())

    async def deactivate_event(self, event_id: int) -> bool:
        """Mark event as inactive (soft delete)."""
        result = await self.db.execute(
            select(Event).where(Event.id == event_id)
        )
        event = result.scalar_one_or_none()

        if event:
            event.is_active = False
            await self.db.commit()
            return True
        return False
