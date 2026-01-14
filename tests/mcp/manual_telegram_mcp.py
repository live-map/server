"""
Telegram MCP 클라이언트 테스트

사용법:
    uv run python -m tests.mcp.test_telegram_mcp
    uv run python -m tests.mcp.test_telegram_mcp --quick
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def test_mcp_client():
    """MCP 클라이언트를 통한 Telegram 도구 테스트"""
    server_script = Path(__file__).parent.parent.parent / "app" / "mcp" / "telegram_server.py"

    if not server_script.exists():
        print(f"Error: Server script not found at {server_script}")
        return

    print("=== Telegram MCP 클라이언트 테스트 ===\n")

    server_params = StdioServerParameters(command=sys.executable, args=[str(server_script)], env=None)

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                print("MCP 서버 연결 성공!\n")

                tools_result = await session.list_tools()
                print("=== 사용 가능한 도구 ===")
                for tool in tools_result.tools:
                    print(f"- {tool.name}: {tool.description}")
                print()

                while True:
                    print("\n" + "=" * 50)
                    print("테스트 메뉴:")
                    print("1. 채널 목록 가져오기 (list_channels)")
                    print("2. 채널 메시지 가져오기 (get_channel_messages)")
                    print("3. 채널 내 검색 (search_channel)")
                    print("4. 채널 정보 가져오기 (get_channel_info)")
                    print("5. 종료")
                    print("=" * 50)

                    choice = input("\n선택: ").strip()

                    if choice == "1":
                        print("\n채널 목록을 가져오는 중...")
                        result = await session.call_tool("list_channels", {})
                        print("\n결과:")
                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    data = json.loads(content.text)
                                    for ch in data[:10]:
                                        print(f"  - [{ch['type']}] {ch['name']} (@{ch.get('username', 'N/A')})")
                                    if len(data) > 10:
                                        print(f"  ... 외 {len(data) - 10}개")
                                except json.JSONDecodeError:
                                    print(content.text)

                    elif choice == "2":
                        channel = input("채널 username 또는 ID: ").strip()
                        limit = input("가져올 메시지 수 (기본 10): ").strip()
                        limit = int(limit) if limit else 10

                        print(f"\n'{channel}' 채널 메시지를 가져오는 중...")
                        result = await session.call_tool(
                            "get_channel_messages", {"channel": channel, "limit": limit, "hours_ago": 24}
                        )

                        print("\n결과:")
                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    data = json.loads(content.text)
                                    print(f"채널: {data.get('channel_name')}")
                                    print(f"메시지 수: {data.get('messages_count')}\n")
                                    for msg in data.get("messages", [])[:5]:
                                        print(f"[{msg['date'][:16]}] 조회: {msg.get('views', 0)}")
                                        text = msg.get("text", "")[:150]
                                        if text:
                                            print(f"  {text}...")
                                        print()
                                except json.JSONDecodeError:
                                    print(content.text)

                    elif choice == "3":
                        channel = input("채널 username 또는 ID: ").strip()
                        query = input("검색어: ").strip()

                        print(f"\n'{channel}'에서 '{query}' 검색 중...")
                        result = await session.call_tool("search_channel", {"channel": channel, "query": query, "limit": 5})

                        print("\n결과:")
                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    data = json.loads(content.text)
                                    print(f"검색 결과: {data.get('results_count')}개\n")
                                    for r in data.get("results", []):
                                        print(f"[{r['date'][:16]}]")
                                        print(f"  {r['text'][:200]}...\n")
                                except json.JSONDecodeError:
                                    print(content.text)

                    elif choice == "4":
                        channel = input("채널 username 또는 ID: ").strip()

                        print(f"\n'{channel}' 정보를 가져오는 중...")
                        result = await session.call_tool("get_channel_info", {"channel": channel})

                        print("\n결과:")
                        for content in result.content:
                            if hasattr(content, "text"):
                                try:
                                    data = json.loads(content.text)
                                    print(json.dumps(data, ensure_ascii=False, indent=2))
                                except json.JSONDecodeError:
                                    print(content.text)

                    elif choice == "5":
                        print("종료합니다.")
                        break
                    else:
                        print("잘못된 선택입니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback

        traceback.print_exc()


async def quick_test():
    """빠른 자동 테스트"""
    server_script = Path(__file__).parent.parent.parent / "app" / "mcp" / "telegram_server.py"
    server_params = StdioServerParameters(command=sys.executable, args=[str(server_script)])

    print("=== 빠른 MCP 테스트 ===\n")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("1. MCP 서버 연결: OK")

            tools = await session.list_tools()
            print(f"2. 도구 목록 가져오기: {len(tools.tools)}개 도구 발견")
            for t in tools.tools:
                print(f"   - {t.name}")

            print("\n3. 채널 목록 테스트...")
            result = await session.call_tool("list_channels", {})
            for content in result.content:
                if hasattr(content, "text"):
                    if "Error" in content.text:
                        print(f"   결과: {content.text}")
                    else:
                        data = json.loads(content.text)
                        print(f"   결과: {len(data)}개 채널 발견")

    print("\n테스트 완료!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="빠른 자동 테스트 실행")
    args = parser.parse_args()

    if args.quick:
        asyncio.run(quick_test())
    else:
        asyncio.run(test_mcp_client())
