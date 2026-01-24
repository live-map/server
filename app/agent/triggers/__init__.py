"""
다중 트리거 시스템

트리거 소스:
1. GDELT - 뉴스 (무료, 15분 딜레이)
2. X/Twitter - 실시간 (Twikit, 개인계정)
3. Telegram - 실시간 (Telethon, 가입채널)
4. P1: Currents API - 뉴스 (1000회/일)
5. P1: World News API - 뉴스 (500회/일)

감지 레이어:
1. Anomaly Detection - 볼륨/속도 이상 감지 (키워드 무관)
2. Semantic Clustering - 새로운 주제 클러스터 감지

각 트리거는 독립적으로 작동하며, TriggerManager가 통합 관리
"""

from .base import BaseTrigger, TriggerEvent, TriggerSource
from .gdelt import GDELTTrigger
from .twitter import TwitterTrigger
from .telegram import TelegramTrigger
from .currents import CurrentsTrigger
from .worldnews import WorldNewsTrigger
from .manager import TriggerManager
from .anomaly import AnomalyDetector, AnomalySignal
from .clustering import SemanticClusterer, SemanticCluster, ClusteringSignal

__all__ = [
    # Base
    "BaseTrigger",
    "TriggerEvent",
    "TriggerSource",
    # Triggers
    "GDELTTrigger",
    "TwitterTrigger",
    "TelegramTrigger",
    "CurrentsTrigger",
    "WorldNewsTrigger",
    "TriggerManager",
    # Detection Layers
    "AnomalyDetector",
    "AnomalySignal",
    "SemanticClusterer",
    "SemanticCluster",
    "ClusteringSignal",
]
