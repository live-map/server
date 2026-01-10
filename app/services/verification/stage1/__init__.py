"""
Stage 1: Local NLP verification.

All processing is done locally with no API calls (free).
- spaCy NER: Location extraction
- Sentence Transformers: Duplicate detection
- TextBlob: Subjectivity analysis
- BERT: Fake news detection
"""

from app.services.verification.stage1.pipeline import Stage1Result, run_stage1

__all__ = ["Stage1Result", "run_stage1"]
