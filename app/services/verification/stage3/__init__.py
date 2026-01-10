"""
Stage 3: LLM verification using Mistral Small.

Deep analysis for claims that passed Stage 1 and 2 without conclusive results.
Cost: ~$0.10/1M input tokens, ~$0.30/1M output tokens (~$0.00014 per request)
"""

from app.services.verification.stage3.pipeline import Stage3Result, run_stage3

__all__ = ["Stage3Result", "run_stage3"]
