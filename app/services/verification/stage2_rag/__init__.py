"""
Stage 2 RAG-based verification pipeline.

Uses SearXNG for evidence retrieval and NLI model for claim verification.
"""

from app.services.verification.stage2_rag.pipeline import RAGVerificationPipeline
from app.services.verification.stage2_rag.models import RAGVerificationResult

__all__ = ["RAGVerificationPipeline", "RAGVerificationResult"]
