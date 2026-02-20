"""
ResearchService — DB 연동 오케스트레이터.

LangGraph 리서치 그래프를 실행하고 결과를 DB에 저장합니다.
v3: astream 기반 실시간 스텝 트래킹 + Unsplash 썸네일.
"""

import asyncio
import logging
import time
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
from app.services.research.tools.unsplash_client import fetch_thumbnail

logger = logging.getLogger(__name__)

# 리서치 상태 추적 (in-memory, TTL 기반)
_research_status: dict[str, dict] = {}
_RESEARCH_STATUS_TTL = 86400  # 24시간

# 노드 → 스텝 매핑
_NODE_TO_STEP = {
    "perspective_discovery": "planning",
    "planner": "planning",
    "web_search": "searching",
    "academic_search": "searching",
    "fact_check": "searching",
    "gap_analyzer": "searching",
    "outline_generator": "analyzing",
    "synthesizer": "analyzing",
    "reviewer": "reviewing",
}

# operator.add로 누적되는 state 키 (astream에서 수동 누적 필요)
_ADDITIVE_KEYS = {"web_sources", "academic_sources", "fact_check_results"}


def _evict_stale_statuses() -> None:
    """TTL이 만료된 리서치 상태를 제거합니다."""
    now = time.monotonic()
    expired = [
        k for k, v in _research_status.items()
        if now - v.get("_ts", 0) > _RESEARCH_STATUS_TTL
    ]
    for k in expired:
        del _research_status[k]


class ResearchService:
    """팩트 리서치 에이전트 서비스."""

    def __init__(self) -> None:
        self.graph = build_research_graph()

    @property
    def enabled(self) -> bool:
        return ai_settings.research_enabled

    def get_status(self, poll_id: str) -> dict:
        """리서치 상태를 조회합니다."""
        _evict_stale_statuses()
        entry = _research_status.get(poll_id)
        if entry is None:
            return {"status": "pending", "error": None, "current_step": None}
        return {
            "status": entry["status"],
            "error": entry.get("error"),
            "current_step": entry.get("current_step"),
        }

    async def run_research(self, poll_id: uuid.UUID, session: AsyncSession) -> None:
        """
        여론조사에 대한 팩트 리서치를 실행합니다.

        BackgroundTasks에서 호출됩니다.
        astream으로 실시간 스텝 트래킹.
        """
        poll_id_str = str(poll_id)
        _research_status[poll_id_str] = {
            "status": "running",
            "error": None,
            "current_step": "planning",
            "_ts": time.monotonic(),
        }

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
                    "_ts": time.monotonic(),
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
                "confidence": 0.0,
                "review_score": 0,
                "error": "",
            }

            logger.info("[Research] Starting research for poll: %s", poll.title[:50])

            # 그래프 실행 (astream으로 실시간 스텝 트래킹, 5분 타임아웃)
            accumulated_state: dict = dict(initial_state)
            try:
                async def _run_stream():
                    async for chunk in self.graph.astream(
                        initial_state,
                        stream_mode="updates",
                    ):
                        # chunk: {node_name: state_update}
                        for node_name, node_output in chunk.items():
                            step = _NODE_TO_STEP.get(node_name)
                            if step:
                                _research_status[poll_id_str]["current_step"] = step
                                logger.debug(
                                    "[Research] Node '%s' completed → step '%s'",
                                    node_name, step,
                                )
                            # 수동 state 누적 (operator.add 키는 append, 나머지는 replace)
                            for key, value in node_output.items():
                                if key in _ADDITIVE_KEYS and isinstance(accumulated_state.get(key), list):
                                    accumulated_state[key] = accumulated_state[key] + value
                                else:
                                    accumulated_state[key] = value

                await asyncio.wait_for(_run_stream(), timeout=300)
            except asyncio.TimeoutError:
                _research_status[poll_id_str] = {
                    "status": "failed",
                    "error": "Research timed out after 300 seconds",
                    "_ts": time.monotonic(),
                }
                logger.error("[Research] Timed out for poll %s", poll_id_str)
                return

            # 결과 저장
            article = accumulated_state.get("final_article") or accumulated_state.get("draft_article", "")
            sources = accumulated_state.get("extracted_sources", [])

            if not article:
                _research_status[poll_id_str] = {
                    "status": "failed",
                    "error": "No article generated",
                    "_ts": time.monotonic(),
                }
                return

            # ai_content + ai_metrics 업데이트
            poll.ai_content = article
            poll.ai_updated_at = datetime.now(timezone.utc)
            poll.ai_metrics = {
                "confidence": accumulated_state.get("confidence", {}),
                "review_score": accumulated_state.get("review_score", 0),
                "retry_count": accumulated_state.get("retry_count", 0),
                "source_count": len(sources),
            }

            # Unsplash 썸네일 자동 설정
            if not poll.image_url:
                try:
                    thumbnail_url = await fetch_thumbnail(poll.title)
                    if thumbnail_url:
                        poll.image_url = thumbnail_url
                        logger.info("[Research] Set thumbnail for poll %s", poll_id_str)
                except Exception as e:
                    logger.warning("[Research] Thumbnail fetch failed: %s", e)

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

            _research_status[poll_id_str] = {"status": "completed", "error": None, "_ts": time.monotonic()}
            logger.info(
                "[Research] Completed for poll %s: %d chars, %d sources",
                poll_id_str, len(article), len(sources),
            )

        except Exception as e:
            logger.error("[Research] Failed for poll %s: %s", poll_id_str, e, exc_info=True)
            _research_status[poll_id_str] = {
                "status": "failed",
                "error": str(e),
                "_ts": time.monotonic(),
            }
            try:
                await session.rollback()
            except Exception:
                pass
