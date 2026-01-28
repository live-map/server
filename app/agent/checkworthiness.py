"""
Check-worthiness 감지 모듈 (Gate 1)

DEPRECATED: This module is deprecated in favor of LLM-based classification.
See llm_classifier.py for the new implementation.

When llm_classifier_enabled=True in config.py:
- LLM replaces this module (Gate 1: checkworthiness)
- Single LLM call determines: is_news (filters entertainment, speculation, etc.)
- Cost: ~$3-5/month for ~2000 articles/day

This file is kept for backward compatibility and fallback mode.

---

목적: 연예, 추측, 일반 배경 콘텐츠 거부

Based on 2026 fact-checking research:
- Check-worthiness = "claims the general public would want to know the truth of"
- Filter out: entertainment, speculation, promotional, background content

P1 Fix: Uses centralized patterns from patterns.py to reduce duplication.
"""

import re
from dataclasses import dataclass
from enum import Enum

# P1 Fix: Import centralized compiled patterns
from .patterns import (
    COMPILED_ENTERTAINMENT_PATTERNS,
    COMPILED_ENTERTAINMENT_CONTEXT_PATTERNS,  # P0 Fix: Context-aware entertainment detection
    COMPILED_SPECULATION_PATTERNS,
    COMPILED_PROMOTIONAL_PATTERNS,
    COMPILED_HUMAN_INTEREST_PATTERNS,
    COMPILED_LOCAL_INCIDENT_PATTERNS,
    COMPILED_SPORTS_PATTERNS,
    COMPILED_LOCAL_CRIME_PATTERNS,
    COMPILED_SIGNIFICANCE_PATTERNS,
    matches_any_pattern,
)


class RejectionReason(Enum):
    ENTERTAINMENT = "entertainment"      # 연예/스포츠/라이프스타일
    SPECULATION = "speculation"          # 추측/의견/미래 예측
    BACKGROUND = "background"            # 일반 배경/역사
    PROMOTIONAL = "promotional"          # 광고/홍보
    HUMAN_INTEREST = "human_interest"    # 인물 특집/미담 기사
    LOCAL_INCIDENT = "local_incident"    # 로컬 사건 (교통사고, 지역 범죄 등)
    SPORTS_NEWS = "sports_news"          # 스포츠 뉴스 (P0 추가)
    LOCAL_CRIME = "local_crime"          # 로컬 범죄 (P0 추가)
    NONE = "none"                        # 거부 사유 없음


@dataclass
class CheckWorthinessResult:
    is_checkworthy: bool
    rejection_reason: RejectionReason
    confidence: float
    matched_patterns: list[str]


# P1 Fix: Pattern definitions moved to patterns.py
# All patterns now imported from centralized module for:
# - Single source of truth
# - Pre-compiled patterns for performance
# - Reduced code duplication


def check_significance(text: str) -> tuple[bool, int, list[str]]:
    """
    Check if event has international significance.

    P1 Fix: Uses pre-compiled patterns from patterns.py.

    Args:
        text: Text to check

    Returns:
        (is_significant, indicator_count, matched_patterns)
    """
    matched = []
    for pattern in COMPILED_SIGNIFICANCE_PATTERNS:
        if pattern.search(text):
            matched.append(pattern.pattern)
    return len(matched) >= 1, len(matched), matched


def check_worthiness(
    text: str,
    entertainment_threshold: int = 2,
    speculation_threshold: int = 2,
    human_interest_threshold: int = 3,
    local_incident_threshold: int = 2,
    sports_threshold: int = 2,
    crime_threshold: int = 2,
) -> CheckWorthinessResult:
    """
    텍스트의 check-worthiness 평가

    P1 Fix: Uses pre-compiled patterns from patterns.py for better performance
    and reduced duplication.

    Args:
        text: 평가할 텍스트
        entertainment_threshold: 연예 패턴 매칭 임계값
        speculation_threshold: 추측 패턴 매칭 임계값
        human_interest_threshold: 인물 특집/미담 패턴 매칭 임계값
        local_incident_threshold: 로컬 사건 패턴 매칭 임계값
        sports_threshold: 스포츠 패턴 매칭 임계값 (P0 추가)
        crime_threshold: 범죄 패턴 매칭 임계값 (P0 추가)

    Returns:
        CheckWorthinessResult with is_checkworthy, rejection_reason, confidence
    """
    # ============================================
    # P1 Fix: Use pre-compiled patterns from patterns.py
    # ============================================

    # Helper to count matches using compiled patterns
    def count_matches(compiled_patterns: list, text: str) -> tuple[int, list[str]]:
        matches = []
        for pattern in compiled_patterns:
            if pattern.search(text):
                matches.append(pattern.pattern)
        return len(matches), matches

    # ============================================
    # P0 추가: 스포츠 뉴스 패턴 체크 (최우선)
    # ============================================
    sports_count, sports_matches = count_matches(COMPILED_SPORTS_PATTERNS, text)
    if sports_count >= sports_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.SPORTS_NEWS,
            confidence=0.95,
            matched_patterns=[f"sports:{p}" for p in sports_matches]
        )

    # ============================================
    # P0 Fix: Entertainment context patterns (movie rankings, celebrity news)
    # Catches cases like "7 Great Sci-Fi War Movies, Ranked" that would
    # otherwise be misclassified as war/conflict news
    # ============================================
    ent_context_count, ent_context_matches = count_matches(COMPILED_ENTERTAINMENT_CONTEXT_PATTERNS, text)
    if ent_context_count >= 1:  # Just 1 match is enough for context-aware detection
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.ENTERTAINMENT,
            confidence=0.90,
            matched_patterns=[f"entertainment_context:{p}" for p in ent_context_matches]
        )

    # ============================================
    # P0 추가: 로컬 범죄 패턴 체크
    # ============================================
    crime_count, crime_matches = count_matches(COMPILED_LOCAL_CRIME_PATTERNS, text)
    if crime_count >= crime_threshold:
        # 국제적 중요성 체크 (override 가능)
        is_significant, sig_count, _ = check_significance(text)
        if not is_significant:
            return CheckWorthinessResult(
                is_checkworthy=False,
                rejection_reason=RejectionReason.LOCAL_CRIME,
                confidence=0.90,
                matched_patterns=[f"crime:{p}" for p in crime_matches]
            )

    # 연예 패턴 체크
    ent_count, ent_matches = count_matches(COMPILED_ENTERTAINMENT_PATTERNS, text)
    if ent_count >= entertainment_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.ENTERTAINMENT,
            confidence=0.9,
            matched_patterns=[f"entertainment:{p}" for p in ent_matches]
        )

    # 추측 패턴 체크
    spec_count, spec_matches = count_matches(COMPILED_SPECULATION_PATTERNS, text)
    if spec_count >= speculation_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.SPECULATION,
            confidence=0.85,
            matched_patterns=[f"speculation:{p}" for p in spec_matches]
        )

    # 홍보 패턴 체크
    promo_count, promo_matches = count_matches(COMPILED_PROMOTIONAL_PATTERNS, text)
    if promo_count >= 1:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.PROMOTIONAL,
            confidence=0.95,
            matched_patterns=[f"promotional:{p}" for p in promo_matches]
        )

    # 인물 특집/미담 패턴 체크 (Human Interest)
    hi_count, hi_matches = count_matches(COMPILED_HUMAN_INTEREST_PATTERNS, text)
    if hi_count >= human_interest_threshold:
        return CheckWorthinessResult(
            is_checkworthy=False,
            rejection_reason=RejectionReason.HUMAN_INTEREST,
            confidence=0.85,
            matched_patterns=[f"human_interest:{p}" for p in hi_matches]
        )

    # ============================================
    # 로컬 사건 패턴 체크 (방어선 3) + Significance Override (방어선 4)
    # ============================================
    local_count, local_matches = count_matches(COMPILED_LOCAL_INCIDENT_PATTERNS, text)

    if local_count >= local_incident_threshold:
        # 로컬 사건 패턴 매칭됨 - significance 체크
        is_significant, sig_count, _ = check_significance(text)

        if is_significant:
            # Significance indicator가 있으면 통과 (대형 사고 등)
            return CheckWorthinessResult(
                is_checkworthy=True,
                rejection_reason=RejectionReason.NONE,
                confidence=0.8,
                matched_patterns=[
                    f"local_patterns:{local_count}",
                    f"significance_override:{sig_count}",
                ]
            )
        else:
            # 로컬 사건이고 significance 없음 - 거부
            return CheckWorthinessResult(
                is_checkworthy=False,
                rejection_reason=RejectionReason.LOCAL_INCIDENT,
                confidence=0.85,
                matched_patterns=[f"local_incident:{p}" for p in local_matches]
            )

    return CheckWorthinessResult(
        is_checkworthy=True,
        rejection_reason=RejectionReason.NONE,
        confidence=1.0,
        matched_patterns=[]
    )
