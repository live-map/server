"""
ResearchService — DB 연동 오케스트레이터.

LangGraph 리서치 그래프를 실행하고 결과를 DB에 저장합니다.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.poll import Poll
from app.models.poll_source import PollSource
from app.services.research.config import ai_settings
from app.services.research.graph import build_research_graph
from app.services.research.state import ResearchState

logger = logging.getLogger(__name__)

# 리서치 상태 추적 (in-memory)
_research_status: dict[str, dict] = {}


class ResearchService:
    """팩트 리서치 에이전트 서비스."""

    def __init__(self) -> None:
        self.graph = build_research_graph()

    @property
    def enabled(self) -> bool:
        return ai_settings.research_enabled

    def get_status(self, poll_id: str) -> dict:
        """리서치 상태를 조회합니다."""
        return _research_status.get(poll_id, {"status": "pending", "error": None})

    async def run_research(self, poll_id: uuid.UUID, session: AsyncSession) -> None:
        """
        여론조사에 대한 팩트 리서치를 실행합니다.

        BackgroundTasks에서 호출됩니다.
        """
        poll_id_str = str(poll_id)
        _research_status[poll_id_str] = {"status": "running", "error": None}

        try:
            # Poll 조회
            stmt = (
                select(Poll)
                .options(selectinload(Poll.options))
                .where(Poll.id == poll_id, Poll.is_deleted.is_(False))
            )
            result = await session.execute(stmt)
            poll = result.scalar_one_or_none()

            if poll is None:
                _research_status[poll_id_str] = {
                    "status": "failed",
                    "error": f"Poll {poll_id} not found",
                }
                return

            # 초기 상태 구성
            initial_state: ResearchState = {
                "poll_id": poll_id_str,
                "poll_title": poll.title,
                "poll_description": poll.description or "",
                "poll_options": [o.text for o in poll.options],
                "poll_category": poll.category or "",
                # NEW: 관점 발견
                "perspectives": [],
                # Planner
                "search_queries": [],
                "academic_queries": [],
                "fact_check_claims": [],
                # 검색 결과
                "web_sources": [],
                "academic_sources": [],
                "fact_check_results": [],
                # NEW: Gap analysis
                "gap_report": {},
                # NEW: Outline
                "outline": [],
                # 합성
                "draft_article": "",
                "review_feedback": "",
                "final_article": "",
                "extracted_sources": [],
                # 제어
                "retry_count": 0,
                "error": "",
            }

            logger.info(f"[Research] Starting research for poll: {poll.title[:50]}")

            # 그래프 실행
            final_state = await self.graph.ainvoke(initial_state)

            # 결과 저장
            article = final_state.get("final_article") or final_state.get("draft_article", "")
            sources = final_state.get("extracted_sources", [])

            if not article:
                _research_status[poll_id_str] = {
                    "status": "failed",
                    "error": "No article generated",
                }
                return

            # ai_content 업데이트
            poll.ai_content = article
            poll.ai_updated_at = datetime.now(timezone.utc)

            # 기존 AI 생성 소스 삭제 후 새로 추가
            existing_sources = await session.execute(
                select(PollSource).where(PollSource.poll_id == poll_id)
            )
            for existing in existing_sources.scalars():
                await session.delete(existing)
            await session.flush()

            # 새 소스 추가
            for src in sources[:20]:  # 최대 20개
                source_type = src.get("source_type", "OTHER")
                if source_type not in ("NEWS", "PAPER", "ARTICLE", "VIDEO", "OTHER"):
                    source_type = "OTHER"

                poll_source = PollSource(
                    poll_id=poll_id,
                    title=src.get("title", "")[:200],
                    url=src.get("url", ""),
                    source_type=source_type,
                    description=src.get("description", "")[:500] if src.get("description") else None,
                )
                session.add(poll_source)

            await session.commit()

            _research_status[poll_id_str] = {"status": "completed", "error": None}
            logger.info(
                f"[Research] Completed for poll {poll_id_str}: "
                f"{len(article)} chars, {len(sources)} sources"
            )

        except Exception as e:
            logger.error(f"[Research] Failed for poll {poll_id_str}: {e}", exc_info=True)
            _research_status[poll_id_str] = {
                "status": "failed",
                "error": str(e),
            }
            try:
                await session.rollback()
            except Exception:
                pass
