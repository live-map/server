"""
Telegram channel message collector.

Collects messages from configured Telegram channels and processes them
through the verification pipeline.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import Channel, Message

from app.core.config import settings

logger = logging.getLogger(__name__)

# Session file path
SESSION_PATH = Path(__file__).parent.parent.parent.parent / "telegram_session"

# Default channels to monitor (can be overridden via config)
DEFAULT_CHANNELS = [
    # Add channel usernames or IDs here
    # "ukraine_war_news",
    # "military_news",
]


@dataclass
class CollectedMessage:
    """A message collected from Telegram."""

    channel_id: int
    channel_name: str
    message_id: int
    text: str
    date: datetime
    views: int | None = None
    forwards: int | None = None
    has_media: bool = False
    media_type: str | None = None


class TelegramCollector:
    """Collects messages from Telegram channels."""

    def __init__(
        self,
        api_id: str | None = None,
        api_hash: str | None = None,
        phone: str | None = None,
        session_path: Path | None = None,
    ):
        self.api_id = api_id or settings.TELEGRAM_API_ID
        self.api_hash = api_hash or settings.TELEGRAM_API_HASH
        self.phone = phone or settings.TELEGRAM_PHONE
        self.session_path = session_path or SESSION_PATH
        self._client: TelegramClient | None = None

    @property
    def is_configured(self) -> bool:
        """Check if Telegram credentials are configured."""
        return all([self.api_id, self.api_hash, self.phone])

    async def connect(self) -> TelegramClient:
        """Connect to Telegram."""
        if not self.is_configured:
            raise RuntimeError("Telegram credentials not configured in .env")

        if self._client is None or not self._client.is_connected():
            self._client = TelegramClient(
                str(self.session_path),
                int(self.api_id),
                self.api_hash,
            )
            await self._client.start(phone=self.phone)
            logger.info("Connected to Telegram")

        return self._client

    async def disconnect(self):
        """Disconnect from Telegram."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.info("Disconnected from Telegram")

    async def list_channels(self) -> list[dict]:
        """List all joined channels."""
        client = await self.connect()
        channels = []

        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, Channel):
                channels.append(
                    {
                        "id": entity.id,
                        "name": dialog.name,
                        "username": entity.username,
                        "type": "channel" if entity.broadcast else "group",
                    }
                )

        return channels

    async def collect_messages(
        self,
        channel: str | int,
        limit: int = 50,
        hours_ago: int = 1,
    ) -> list[CollectedMessage]:
        """
        Collect recent messages from a channel.

        Args:
            channel: Channel username or ID
            limit: Maximum messages to fetch
            hours_ago: Only get messages from last N hours

        Returns:
            List of collected messages
        """
        client = await self.connect()

        try:
            # Get channel entity
            if isinstance(channel, str) and channel.isdigit():
                channel = int(channel)
            entity = await client.get_entity(channel)
        except Exception as e:
            logger.error(f"Failed to get channel {channel}: {e}")
            return []

        min_date = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        messages = []

        try:
            async for message in client.iter_messages(entity, limit=limit):
                if not isinstance(message, Message):
                    continue

                # Skip old messages
                if message.date < min_date:
                    break

                # Skip empty messages
                if not message.text:
                    continue

                messages.append(
                    CollectedMessage(
                        channel_id=entity.id,
                        channel_name=getattr(entity, "title", str(entity.id)),
                        message_id=message.id,
                        text=message.text,
                        date=message.date,
                        views=message.views,
                        forwards=message.forwards,
                        has_media=message.media is not None,
                        media_type=type(message.media).__name__ if message.media else None,
                    )
                )

            logger.info(f"Collected {len(messages)} messages from {channel}")
            return messages

        except Exception as e:
            logger.error(f"Failed to collect from {channel}: {e}")
            return []

    async def collect_from_channels(
        self,
        channels: list[str | int] | None = None,
        limit_per_channel: int = 50,
        hours_ago: int = 1,
    ) -> list[CollectedMessage]:
        """
        Collect messages from multiple channels.

        Args:
            channels: List of channel usernames or IDs (uses DEFAULT_CHANNELS if None)
            limit_per_channel: Max messages per channel
            hours_ago: Time window

        Returns:
            All collected messages
        """
        channels = channels or DEFAULT_CHANNELS

        if not channels:
            logger.warning("No channels configured for collection")
            return []

        all_messages = []

        for channel in channels:
            messages = await self.collect_messages(
                channel=channel,
                limit=limit_per_channel,
                hours_ago=hours_ago,
            )
            all_messages.extend(messages)

        logger.info(f"Total collected: {len(all_messages)} messages from {len(channels)} channels")
        return all_messages
