"""
Stage 2: RAG-based Evidence Verification.

신규 뉴스 교차 검증:
- SearXNG: 다른 뉴스 소스 검색
- mDeBERTa NLI: 주장-증거 매칭
- CRAG: 품질 평가 및 교정적 검색
"""

from app.services.verification.stage2.pipeline import Stage2Result, run_stage2

__all__ = ["Stage2Result", "run_stage2"]
