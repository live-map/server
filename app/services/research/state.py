"""
LangGraph state definitions for the Research Agent.

리서치 에이전트의 상태(State) 타입을 정의합니다.

v2: perspectives, outline, gap_report 추가.
"""

import operator
from typing import Annotated, TypedDict


class SourceItem(TypedDict):
    """수집된 출처 정보."""

    title: str
    url: str
    source_type: str  # NEWS | PAPER | ARTICLE | OTHER
    description: str
    content_snippet: str  # 검색에서 추출한 원문 일부
    credibility: str  # HIGH | MEDIUM | LOW


class Perspective(TypedDict):
    """발견된 관점/이해관계자."""

    label: str
    description: str
    key_questions: list[str]


class OutlineSection(TypedDict):
    """아웃라인 섹션."""

    title: str
    key_points: list[str]
    source_numbers: list[int]


class ResearchState(TypedDict):
    """LangGraph 리서치 에이전트 전체 상태."""

    # 입력 (poll 정보)
    poll_id: str
    poll_title: str
    poll_description: str
    poll_options: list[str]
    poll_category: str

    # NEW: 관점 발견
    perspectives: list[Perspective]

    # Planner 출력
    search_queries: list[str]
    academic_queries: list[str]
    fact_check_claims: list[str]

    # 검색 결과 (append-only via operator.add)
    web_sources: Annotated[list[SourceItem], operator.add]
    academic_sources: Annotated[list[SourceItem], operator.add]
    fact_check_results: Annotated[list[dict], operator.add]

    # NEW: Gap analysis
    gap_report: dict

    # NEW: Outline
    outline: list[OutlineSection]

    # 합성
    draft_article: str
    review_feedback: str
    final_article: str
    extracted_sources: list[SourceItem]
    confidence: dict

    # Citation 검증
    citation_issues: list[str]

    # 리뷰
    review_score: int

    # 제어
    retry_count: int
    error: str
