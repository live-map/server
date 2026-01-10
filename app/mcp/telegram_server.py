"""
Telegram MCP Server

Telegram 채널/그룹에서 메시지를 수집하는 MCP 서버입니다.

사용법:
    uv run python -m app.mcp.telegram_server
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from telethon import TelegramClient
from telethon.tl.types import Channel, Message

# 환경 변수 로드
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_PATH = Path(__file__).parent.parent.parent / "telegram_session"

# MCP 서버 생성
server = Server("telegram-mcp")

# 전역 Telegram 클라이언트
_client: TelegramClient | None = None


async def get_client() -> TelegramClient:
    """Telegram 클라이언트 싱글톤"""
    global _client
    if _client is None or not _client.is_connected():
        _client = TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)
        await _client.start(phone=PHONE)
    return _client


@server.list_tools()
async def list_tools():
    """사용 가능한 도구 목록"""
    return [
        Tool(
            name="list_channels",
            description="참여한 Telegram 채널/그룹 목록을 가져옵니다",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="get_channel_messages",
            description="특정 채널의 최근 메시지를 가져옵니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "채널 username (@없이) 또는 채널 ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "가져올 메시지 수 (기본 20)",
                        "default": 20,
                    },
                    "hours_ago": {
                        "type": "integer",
                        "description": "몇 시간 전 메시지까지 (기본 24)",
                        "default": 24,
                    },
                },
                "required": ["channel"],
            },
        ),
        Tool(
            name="search_channel",
            description="채널 내에서 키워드로 메시지를 검색합니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "채널 username 또는 ID"},
                    "query": {"type": "string", "description": "검색 키워드"},
                    "limit": {
                        "type": "integer",
                        "description": "결과 수 (기본 10)",
                        "default": 10,
                    },
                },
                "required": ["channel", "query"],
            },
        ),
        Tool(
            name="get_channel_info",
            description="채널의 상세 정보를 가져옵니다",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {"type": "string", "description": "채널 username 또는 ID"}
                },
                "required": ["channel"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """도구 호출 처리"""
    if name == "list_channels":
        return await _list_channels()
    elif name == "get_channel_messages":
        return await _get_channel_messages(
            channel=arguments["channel"],
            limit=arguments.get("limit", 20),
            hours_ago=arguments.get("hours_ago", 24),
        )
    elif name == "search_channel":
        return await _search_channel(
            channel=arguments["channel"],
            query=arguments["query"],
            limit=arguments.get("limit", 10),
        )
    elif name == "get_channel_info":
        return await _get_channel_info(arguments["channel"])
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _list_channels():
    """참여한 채널 목록"""
    try:
        client = await get_client()
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
                        "participants_count": getattr(entity, "participants_count", None),
                    }
                )

        return [TextContent(type="text", text=json.dumps(channels, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def _get_channel_messages(channel: str, limit: int = 20, hours_ago: int = 24):
    """채널 메시지 가져오기"""
    try:
        client = await get_client()

        try:
            entity = await client.get_entity(channel)
        except ValueError:
            entity = await client.get_entity(int(channel))

        min_date = datetime.now() - timedelta(hours=hours_ago)
        messages = []

        async for message in client.iter_messages(entity, limit=limit):
            if not isinstance(message, Message):
                continue

            if message.date.replace(tzinfo=None) < min_date:
                break

            messages.append(
                {
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "text": message.text or "",
                    "views": message.views,
                    "forwards": message.forwards,
                    "has_media": message.media is not None,
                    "media_type": type(message.media).__name__ if message.media else None,
                    "reply_to_msg_id": message.reply_to_msg_id,
                }
            )

        result = {
            "channel": channel,
            "channel_name": entity.title if hasattr(entity, "title") else str(entity),
            "messages_count": len(messages),
            "messages": messages,
        }

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def _search_channel(channel: str, query: str, limit: int = 10):
    """채널 내 검색"""
    try:
        client = await get_client()
        entity = await client.get_entity(channel)

        results = []
        async for message in client.iter_messages(entity, search=query, limit=limit):
            if not message.text:
                continue

            results.append(
                {
                    "id": message.id,
                    "date": message.date.isoformat(),
                    "text": message.text[:500],
                    "views": message.views,
                }
            )

        result = {
            "channel": channel,
            "query": query,
            "results_count": len(results),
            "results": results,
        }

        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def _get_channel_info(channel: str):
    """채널 정보"""
    try:
        client = await get_client()
        entity = await client.get_entity(channel)

        info = {
            "id": entity.id,
            "title": getattr(entity, "title", None),
            "username": getattr(entity, "username", None),
            "is_channel": getattr(entity, "broadcast", False),
            "is_group": not getattr(entity, "broadcast", True),
            "participants_count": getattr(entity, "participants_count", None),
            "photo": entity.photo is not None,
            "verified": getattr(entity, "verified", False),
            "restricted": getattr(entity, "restricted", False),
        }

        return [TextContent(type="text", text=json.dumps(info, ensure_ascii=False, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e!s}")]


async def main():
    """MCP 서버 실행"""
    if not all([API_ID, API_HASH, PHONE]):
        print("Error: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_PHONE을 .env에 설정하세요")
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
