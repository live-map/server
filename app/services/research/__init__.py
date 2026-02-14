"""
Research Agent module for automated fact research on poll topics.

LangGraph 기반의 팩트 리서치 에이전트.
여론조사 주제에 대해 객관적 사실, 학술 자료, 통계를 수집하고
균형 잡힌 아티클을 생성합니다.
"""

from app.services.research.service import ResearchService

__all__ = ["ResearchService"]
