"""
Stage 1: Local NLP verification.

V1 (news articles):
- spaCy NER: Location extraction (required)
- Sentence Transformers: Duplicate detection
- TextBlob: Subjectivity analysis
- BERT: Fake news detection

V2 (social media):
- spaCy NER: Location extraction (optional)
- Sentence Transformers: Duplicate detection (dynamic threshold)
- Channel credibility scoring
- Fake news/subjectivity disabled for short posts
"""

from app.services.verification.stage1.pipeline import (
    Stage1Result,
    Stage1ResultV2,
    load_all_models,
    run_stage1_async,
    run_stage1_v2_async,
)
from app.services.verification.stage1.channel_credibility import (
    ChannelCredibilityResult,
    calculate_channel_credibility,
)

__all__ = [
    # V1 (legacy)
    "Stage1Result",
    "run_stage1_async",
    # V2 (social media)
    "Stage1ResultV2",
    "run_stage1_v2_async",
    "ChannelCredibilityResult",
    "calculate_channel_credibility",
    # Common
    "load_all_models",
]
