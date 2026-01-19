"""
Autonomous Investigation Agent Module

에이전트가 스스로 판단하여:
1. 뉴스 소스를 모니터링하고
2. 중요 사건 발생 시 어떤 소스를 조사할지 결정하고
3. 영상/사진/기사를 수집하고
4. 검증된 리포트를 생성

Canonical Agent:
- InvestigationAgent: Planner-executor-verifier-publisher pipeline
"""

from .investigator import InvestigationAgent
from .scanner import NewsScanner

__all__ = [
    "InvestigationAgent",
    "NewsScanner",
]
