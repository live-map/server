"""
Telegram 로그인

사용법:
    uv run python scripts/telegram_login.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
PHONE = os.getenv("TELEGRAM_PHONE")
SESSION_PATH = Path(__file__).parent.parent / "telegram_session"


async def main():
    print("=" * 50)
    print("Telegram 로그인")
    print("=" * 50)
    print(f"전화번호: {PHONE}")
    print()

    client = TelegramClient(str(SESSION_PATH), API_ID, API_HASH)

    # start()가 알아서 코드 입력 처리함
    await client.start(phone=PHONE)

    me = await client.get_me()
    print()
    print("=" * 50)
    print("로그인 성공!")
    print(f"계정: {me.first_name} (@{me.username})")
    print(f"세션 파일: {SESSION_PATH}.session")
    print("=" * 50)

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
