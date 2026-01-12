"""
Telegram 트리거 - Telethon 기반

특징:
- 무료 (공식 API)
- 가입한 채널만 검색 가능
- 실시간 메시지 모니터링
- 주요 OSINT 채널 사전 가입 필요

설정 필요:
- TELEGRAM_API_ID: https://my.telegram.org/apps
- TELEGRAM_API_HASH: https://my.telegram.org/apps
- TELEGRAM_PHONE: 전화번호 (+821012345678)

권장 채널 (사전 가입):
- @ukrainenowenglish, @nexta_live (우크라이나)
- @IranIntl, @IranHRM (이란)
- @GeoConfirmed, @WarMonitor3 (OSINT)
"""

import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)

# 권장 채널 목록 (사전 가입 필요)
RECOMMENDED_CHANNELS = {
    "osint": [
        "GeoConfirmed",
        "WarMonitor3",
        "intelslava",
        "ukraine_map",
    ],
    "ukraine": [
        "ukrainenowenglish",
        "nexta_live",
        "KyivIndependent",
        "UkraineNow",
    ],
    "iran": [
        "IranIntl",
        "IranHRM",
        "manikifarsi",
    ],
    "middle_east": [
        "AJABreaking",
        "QudsNen",
    ],
}


class TelegramTrigger(BaseTrigger):
    """
    Telegram 트리거 (Telethon 라이브러리 사용)

    가입한 채널에서 새 메시지를 모니터링
    """

    def __init__(
        self,
        api_id: str | None = None,
        api_hash: str | None = None,
        phone: str | None = None,
        session_path: str = "telegram_session",
        channels: list[str] | None = None,
        keywords: list[str] | None = None,
        lookback_minutes: int = 30,
    ):
        super().__init__(keywords)
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_path = session_path
        self.channels = channels or self._get_default_channels()
        self.lookback_minutes = lookback_minutes
        self.client = None
        self.seen_message_ids: set[str] = set()

    def _get_default_channels(self) -> list[str]:
        """기본 채널 목록 (전체)"""
        all_channels = []
        for channels in RECOMMENDED_CHANNELS.values():
            all_channels.extend(channels)
        return all_channels

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.TELEGRAM

    @property
    def source_name(self) -> str:
        return "Telegram"

    async def initialize(self) -> bool:
        """Telethon 클라이언트 초기화"""
        if not self.api_id or not self.api_hash:
            logger.warning("Telegram: API credentials not provided")
            logger.info("Get credentials at: https://my.telegram.org/apps")
            return False

        try:
            from telethon import TelegramClient

            self.client = TelegramClient(
                self.session_path,
                int(self.api_id),
                self.api_hash,
            )

            await self.client.start(phone=self.phone)

            if await self.client.is_user_authorized():
                logger.info("Telegram: Authorized successfully")
                self.is_initialized = True
                return True
            else:
                logger.warning("Telegram: Not authorized, need phone verification")
                return False

        except ImportError:
            logger.error("Telegram: telethon not installed. Run: pip install telethon")
            return False
        except Exception as e:
            logger.error(f"Telegram initialization error: {e}")
            return False

    async def scan(self) -> list[TriggerEvent]:
        """가입한 채널에서 새 메시지 검색"""
        if not self.is_initialized or not self.client:
            logger.warning("Telegram: Not initialized, skipping scan")
            return []

        self.last_scan = datetime.utcnow()
        events = []
        cutoff_time = datetime.utcnow() - timedelta(minutes=self.lookback_minutes)

        for channel_name in self.channels:
            try:
                # 채널 엔티티 가져오기
                channel = await self.client.get_entity(channel_name)

                # 최근 메시지 가져오기
                async for message in self.client.iter_messages(
                    channel,
                    limit=20,
                    offset_date=datetime.utcnow(),
                ):
                    # 시간 필터
                    if message.date.replace(tzinfo=None) < cutoff_time:
                        break

                    # 중복 체크
                    msg_id = f"{channel_name}:{message.id}"
                    if msg_id in self.seen_message_ids:
                        continue
                    self.seen_message_ids.add(msg_id)

                    # 텍스트 추출
                    text = message.text or ""
                    if not text:
                        continue

                    # 키워드 매칭
                    matched = self._matches_keywords(text)

                    if matched:
                        # 미디어 URL 추출
                        media_urls = []
                        if message.media:
                            if hasattr(message.media, 'photo'):
                                media_urls.append(f"telegram_photo:{message.id}")
                            elif hasattr(message.media, 'document'):
                                media_urls.append(f"telegram_doc:{message.id}")

                        events.append(TriggerEvent(
                            title=text[:200],
                            source=TriggerSource.TELEGRAM,
                            source_name=f"@{channel_name}",
                            url=f"https://t.me/{channel_name}/{message.id}",
                            detected_at=message.date.replace(tzinfo=None),
                            content=text,
                            keywords_matched=matched,
                            media_urls=media_urls,
                            raw_data={
                                "message_id": message.id,
                                "channel": channel_name,
                                "views": getattr(message, 'views', 0),
                            },
                        ))

            except Exception as e:
                logger.warning(f"Telegram: Error scanning @{channel_name}: {e}")
                continue

        # 메모리 관리
        if len(self.seen_message_ids) > 5000:
            self.seen_message_ids.clear()

        logger.info(f"Telegram scan: {len(self.channels)} channels, {len(events)} matched")
        return events

    async def close(self):
        """연결 종료"""
        self.seen_message_ids.clear()
        if self.client:
            await self.client.disconnect()
            self.client = None

    @staticmethod
    def get_recommended_channels() -> dict[str, list[str]]:
        """권장 채널 목록 반환"""
        return RECOMMENDED_CHANNELS
