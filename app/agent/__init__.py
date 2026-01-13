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
"""

from .investigator import InvestigationAgent
from .investigator_v2 import DeepVerificationAgent, InvestigationAgentV2
from .scanner import NewsScanner

__all__ = [
    "InvestigationAgent",
    "DeepVerificationAgent",
    "InvestigationAgentV2",
    "NewsScanner",
]
