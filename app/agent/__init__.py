"""
Autonomous Investigation Agent Module

에이전트가 스스로 판단하여:
1. 뉴스 소스를 모니터링하고
2. 중요 사건 발생 시 어떤 소스를 조사할지 결정하고
3. 영상/사진/기사를 수집하고
4. 검증된 리포트를 생성

Agent Versions:
- ClaimVerificationAgent (v3): Claim-level verification with AP Style article generation (PRIMARY)
- InvestigationAgent (v1): Simple planner-executor-verifier-publisher pipeline
"""

from .investigator import InvestigationAgent
from .investigator_v3 import ClaimVerificationAgent, InvestigationAgentV3
from .scanner import NewsScanner

# Claim-level verification components
from .claim_extraction import ClaimExtractor, ExtractedClaim, extract_claims
from .qa_verifier import QAVerifier, ClaimVerdict, VerificationResult, verify_claim
from .article_generator import ArticleGenerator, GeneratedArticle, generate_article

# Bilingual article generation
from .bilingual_article_generator import BilingualArticleGenerator, BilingualArticle, generate_bilingual_article

# Deduplication
from .deduplication import EventMatcher, MatchResult, MatchType, UpdateDetector, UpdateType, UpdateCheckResult

__all__ = [
    # Primary Agent (v3)
    "ClaimVerificationAgent",
    "InvestigationAgentV3",
    # Legacy Agent (v1)
    "InvestigationAgent",
    # Scanner
    "NewsScanner",
    # Claim-level components
    "ClaimExtractor",
    "ExtractedClaim",
    "extract_claims",
    "QAVerifier",
    "ClaimVerdict",
    "VerificationResult",
    "verify_claim",
    "ArticleGenerator",
    "GeneratedArticle",
    "generate_article",
    # Bilingual article generation
    "BilingualArticleGenerator",
    "BilingualArticle",
    "generate_bilingual_article",
    # Deduplication
    "EventMatcher",
    "MatchResult",
    "MatchType",
    "UpdateDetector",
    "UpdateType",
    "UpdateCheckResult",
]
