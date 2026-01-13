"""
Stage 2 RAG-based verification pipeline.

V1: SearXNG for news evidence retrieval + NLI for claim verification
V2: Multi-source search (Telegram + OSINT + News) + NLI
"""

from app.services.verification.stage2_rag.models import (
    Evidence,
    RAGVerdict,
    RAGVerificationResult,
    SourceType,
)
from app.services.verification.stage2_rag.pipeline import (
    RAGVerificationPipeline,
    get_rag_pipeline,
)
from app.services.verification.stage2_rag.telegram_searcher import (
    TelegramSearchResult,
    search_telegram_channels,
)
from app.services.verification.stage2_rag.osint_searcher import (
    OSINTSearchResult,
    search_osint_sources,
)

__all__ = [
    # Models
    "Evidence",
    "RAGVerdict",
    "RAGVerificationResult",
    "SourceType",
    # Pipeline
    "RAGVerificationPipeline",
    "get_rag_pipeline",
    # V2 Searchers
    "TelegramSearchResult",
    "search_telegram_channels",
    "OSINTSearchResult",
    "search_osint_sources",
]
