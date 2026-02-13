"""
Pydantic schemas for LLM structured output.

with_structured_output()에서 사용하는 스키마 정의.
JSON 수동 파싱 대신 95%+ 신뢰도의 구조화된 출력을 보장합니다.
"""

from pydantic import BaseModel, Field


# ── Perspective Discovery ──


class Perspective(BaseModel):
    """발견된 관점/이해관계자."""

    label: str = Field(..., description="관점 라벨 (예: '노동계', '재계')")
    description: str = Field(..., description="관점 설명")
    key_questions: list[str] = Field(
        ...,
        min_length=1,
        max_length=3,
        description="이 관점에서 가장 중요한 질문 1-3개",
    )


class PerspectiveOutput(BaseModel):
    """관점 발견 노드 출력."""

    perspectives: list[Perspective] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="발견된 관점 목록 (3-5개 권장)",
    )


# ── Planner ──


class PlannerOutput(BaseModel):
    """플래너 노드 출력."""

    search_queries: list[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="웹 검색 쿼리 (관점별 2개씩)",
    )
    academic_queries: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="학술 검색 쿼리 (영어)",
    )
    fact_check_claims: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="팩트체크할 핵심 주장",
    )


# ── Gap Analyzer ──


class GapReport(BaseModel):
    """갭 분석 결과."""

    covered_perspectives: list[str] = Field(
        default_factory=list,
        description="충분히 커버된 관점 라벨 목록",
    )
    gap_perspectives: list[str] = Field(
        default_factory=list,
        description="출처가 부족한 관점 라벨 목록",
    )
    follow_up_queries: list[str] = Field(
        default_factory=list,
        max_length=4,
        description="부족한 관점에 대한 추가 검색 쿼리",
    )
    summary: str = Field(default="", description="갭 분석 요약")


# ── Outline Generator ──


class OutlineSection(BaseModel):
    """아웃라인 섹션."""

    title: str = Field(..., description="섹션 제목 (## 포함)")
    key_points: list[str] = Field(
        ...,
        min_length=1,
        max_length=4,
        description="해당 섹션에서 다룰 핵심 포인트",
    )
    source_numbers: list[int] = Field(
        default_factory=list,
        description="인용할 출처 번호",
    )


class OutlineOutput(BaseModel):
    """아웃라인 생성 노드 출력."""

    sections: list[OutlineSection] = Field(
        ...,
        min_length=2,
        max_length=6,
        description="아티클 섹션 (3-5개 권장)",
    )
    structure_rationale: str = Field(
        ...,
        description="이 구조를 선택한 이유",
    )


# ── Reviewer ──


class ReviewerOutput(BaseModel):
    """리뷰어 노드 출력."""

    passed: bool = Field(..., description="아티클 통과 여부")
    score: int = Field(..., ge=0, le=100, description="품질 점수 (0-100)")
    feedback: str = Field(default="", description="수정이 필요한 경우 구체적 피드백")
