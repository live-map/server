"""
Stage 0: Preprocessing module for social media content.

This module handles text normalization, coordinate extraction,
terminology standardization, and repost detection before the
main verification pipeline.
"""

from app.services.verification.stage0_preprocessing.pipeline import (
    Stage0Result,
    run_stage0,
)

__all__ = ["Stage0Result", "run_stage0"]
