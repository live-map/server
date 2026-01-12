"""
다중 트리거 시스템

트리거 소스:
1. GDELT - 뉴스 (무료, 15분 딜레이)
2. X/Twitter - 실시간 (Twikit, 개인계정)
3. Telegram - 실시간 (Telethon, 가입채널)

각 트리거는 독립적으로 작동하며, TriggerManager가 통합 관리
"""

from .base import BaseTrigger, TriggerEvent
from .gdelt import GDELTTrigger
from .twitter import TwitterTrigger
from .telegram import TelegramTrigger
from .manager import TriggerManager

__all__ = [
    "BaseTrigger",
    "TriggerEvent",
    "GDELTTrigger",
    "TwitterTrigger",
    "TelegramTrigger",
    "TriggerManager",
]
