"""
Verification pipeline services.

Simplified pipeline: Stage 1 (NLP) → Stage 3 (LLM)
Stage 2 (SearXNG RAG) has been removed - use autonomous agent instead.
"""

from app.services.verification.pipeline import (
    PipelineResult,
    VerificationStatus,
    run_pipeline,
)
from app.services.verification.stage1 import (
    Stage1Result,
    run_stage1_async,
)
from app.services.verification.stage3 import Stage3Result, run_stage3

__all__ = [
    "PipelineResult",
    "VerificationStatus",
    "run_pipeline",
    "Stage1Result",
    "run_stage1_async",
    "Stage3Result",
    "run_stage3",
]
