"""
Telegram 메시지 수집 테스트 (Telethon 직접 사용)

사용법:
    uv run python -m tests.mcp.test_telegram_direct
"""

import asyncio
import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.types import Channel, Message

# .env 파일 로드
load_dotenv()

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_PATH = Path(__file__).parent.parent.parent / "telegram_session"


async def list_dialogs(client: TelegramClient):
    """참여한 채널/그룹 목록 출력"""
    print("\n=== 참여한 채널/그룹 목록 ===\n")

    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if isinstance(entity, Channel):
            channel_type = "채널" if entity.broadcast else "그룹"
            print(f"[{channel_type}] {dialog.name}")
            print(f"  - ID: {entity.id}")
            print(f"  - Username: @{entity.username}" if entity.username else "  - Username: (없음)")
            print()


async def fetch_channel_messages(
    client: TelegramClient, channel_id: str | int, limit: int = 10, hours_ago: int = 24
):
    """특정 채널의 최근 메시지 수집"""
    print(f"\n=== 채널 '{channel_id}' 메시지 수집 ===\n")

    try:
        if isinstance(channel_id, str) and not channel_id.startswith("-"):
            entity = await client.get_entity(channel_id)
        else:
            entity = await client.get_entity(int(channel_id))

        print(f"채널명: {entity.title if hasattr(entity, 'title') else entity}")
        print(f"ID: {entity.id}")
        print("-" * 50)

        min_date = datetime.now() - timedelta(hours=hours_ago)
        messages = []

        async for message in client.iter_messages(entity, limit=limit, offset_date=datetime.now()):
            if not isinstance(message, Message):
                continue

            if message.date.replace(tzinfo=None) < min_date:
                break

            msg_data = {
                "id": message.id,
                "date": message.date.isoformat(),
                "text": message.text or "",
                "views": message.views,
                "forwards": message.forwards,
                "has_media": message.media is not None,
            }
            messages.append(msg_data)

            print(f"\n[{message.date.strftime('%Y-%m-%d %H:%M')}]")
            print(f"  조회수: {message.views or 0} | 전달: {message.forwards or 0}")
            if message.text:
                preview = message.text[:200] + "..." if len(message.text) > 200 else message.text
                print(f"  내용: {preview}")
            if message.media:
                print("  미디어: 있음")

        print(f"\n총 {len(messages)}개 메시지 수집됨")
        return messages

    except Exception as e:
        print(f"오류 발생: {e}")
        return []


async def search_messages(client: TelegramClient, channel_id: str | int, query: str, limit: int = 10):
    """채널 내 메시지 검색"""
    print(f"\n=== 채널 '{channel_id}'에서 '{query}' 검색 ===\n")

    try:
        entity = await client.get_entity(channel_id)
        results = []

        async for message in client.iter_messages(entity, search=query, limit=limit):
            if not message.text:
                continue

            results.append({"id": message.id, "date": message.date.isoformat(), "text": message.text[:300]})

            print(f"[{message.date.strftime('%Y-%m-%d %H:%M')}]")
            preview = message.text[:200] + "..." if len(message.text) > 200 else message.text
            print(f"  {preview}\n")

        print(f"총 {len(results)}개 검색 결과")
        return results

    except Exception as e:
        print(f"오류 발생: {e}")
        return []


async def main():
    """메인 테스트 함수"""
    if not all([API_ID, API_HASH, PHONE]):
        print("오류: .env 파일에 다음 환경 변수를 설정해주세요:")
        print("  - TELEGRAM_API_ID")
        print("  - TELEGRAM_API_HASH")
        print("  - TELEGRAM_PHONE")
        print("\nhttps://my.telegram.org/apps 에서 발급받을 수 있습니다.")
        return

    print("=== Telegram 연결 테스트 ===")
    print(f"API ID: {API_ID}")
    print(f"Phone: {PHONE}")

    client = TelegramClient(str(SESSION_PATH), int(API_ID), API_HASH)

    try:
        await client.start(phone=PHONE)
        print("\n로그인 성공!")

        me = await client.get_me()
        print(f"로그인된 계정: {me.first_name} (@{me.username})")

        while True:
            print("\n" + "=" * 50)
            print("테스트 메뉴:")
            print("1. 참여한 채널/그룹 목록 보기")
            print("2. 특정 채널 메시지 가져오기")
            print("3. 채널 내 메시지 검색")
            print("4. 종료")
            print("=" * 50)

            choice = input("\n선택: ").strip()

            if choice == "1":
                await list_dialogs(client)
            elif choice == "2":
                channel = input("채널 username 또는 ID: ").strip()
                limit = input("가져올 메시지 수 (기본 10): ").strip()
                limit = int(limit) if limit else 10
                await fetch_channel_messages(client, channel, limit=limit)
            elif choice == "3":
                channel = input("채널 username 또는 ID: ").strip()
                query = input("검색어: ").strip()
                await search_messages(client, channel, query)
            elif choice == "4":
                print("종료합니다.")
                break
            else:
                print("잘못된 선택입니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
