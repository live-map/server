"""
Verification pipeline services.

V1 (news articles): 3-stage pipeline
V2 (social media): 4-stage pipeline with preprocessing and channel credibility
"""

from app.services.verification.pipeline import (
    PipelineResult,
    PipelineResultV2,
    run_pipeline,
    run_pipeline_v2,
    run_pipeline_auto,
)
from app.services.verification.stage0_preprocessing import Stage0Result, run_stage0
from app.services.verification.stage1 import (
    Stage1Result,
    Stage1ResultV2,
    run_stage1_async,
    run_stage1_v2_async,
)
from app.services.verification.stage2 import Stage2Result, run_stage2
from app.services.verification.stage3 import Stage3Result, run_stage3

__all__ = [
    # V1 Pipeline
    "PipelineResult",
    "run_pipeline",
    "Stage1Result",
    "run_stage1_async",
    # V2 Pipeline
    "PipelineResultV2",
    "run_pipeline_v2",
    "run_pipeline_auto",
    "Stage0Result",
    "run_stage0",
    "Stage1ResultV2",
    "run_stage1_v2_async",
    # Common
    "Stage2Result",
    "run_stage2",
    "Stage3Result",
    "run_stage3",
]
