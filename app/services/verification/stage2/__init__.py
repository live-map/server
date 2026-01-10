"""
Stage 2: External API verification.

Free API calls for additional verification:
- ClaimBuster: Check-worthiness scoring
- Google Fact Check: Search existing fact-checks
"""

from app.services.verification.stage2.pipeline import Stage2Result, run_stage2

__all__ = ["Stage2Result", "run_stage2"]
