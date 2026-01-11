"""
Data models for RAG-based verification.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RAGVerdict(Enum):
    """Verdict from RAG verification."""
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    UNCERTAIN = "UNCERTAIN"
    NO_EVIDENCE = "NO_EVIDENCE"


@dataclass
class Evidence:
    """Retrieved evidence from search."""
    text: str
    source: str
    url: str
    title: str
    published_date: datetime | None = None
    relevance_score: float = 0.5
    is_trusted_source: bool = False


@dataclass
class EvidenceCheckResult:
    """Result of checking a claim against evidence."""
    evidence: Evidence
    entailment_score: float  # 0-1, how much evidence supports claim
    contradiction_score: float  # 0-1, how much evidence contradicts claim
    neutral_score: float  # 0-1, neutral/not relevant
    verdict: str  # SUPPORTS, REFUTES, NEUTRAL


@dataclass
class RAGVerificationResult:
    """Final result from RAG verification pipeline."""
    verdict: RAGVerdict
    confidence: float  # 0-1
    evidence_summary: str
    sources: list[dict] = field(default_factory=list)  # [{url, title, snippet}]
    claim_supported_by: int = 0
    claim_refuted_by: int = 0
    total_evidence_found: int = 0
    check_results: list[EvidenceCheckResult] = field(default_factory=list)
    processing_time_ms: int = 0
