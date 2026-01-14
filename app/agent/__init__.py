"""
Autonomous Investigation Agent Module

에이전트가 스스로 판단하여:
1. 뉴스 소스를 모니터링하고
2. 중요 사건 발생 시 어떤 소스를 조사할지 결정하고
3. 영상/사진/기사를 수집하고
4. 검증된 리포트를 생성

Agent Versions:
- InvestigationAgent (v1): Original planner-executor-verifier-publisher
- DeepVerificationAgent (v2): Perplexity-style deep verification with conflict detection
- ClaimVerificationAgent (v3): Claim-level verification (2026 SOTA)
"""

from .investigator import InvestigationAgent
from .investigator_v2 import DeepVerificationAgent, InvestigationAgentV2
from .investigator_v3 import ClaimVerificationAgent, InvestigationAgentV3
from .scanner import NewsScanner

# Claim-level verification components
from .claim_extraction import ClaimExtractor, ExtractedClaim, extract_claims
from .qa_verifier import QAVerifier, ClaimVerdict, VerificationResult, verify_claim
from .article_generator import ArticleGenerator, GeneratedArticle, generate_article

__all__ = [
    # Agents
    "InvestigationAgent",
    "DeepVerificationAgent",
    "InvestigationAgentV2",
    "ClaimVerificationAgent",
    "InvestigationAgentV3",
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
]
