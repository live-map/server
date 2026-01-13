"""
자율 조사 에이전트 (LangGraph)

핵심: 에이전트가 스스로 판단하여
1. 어떤 소스를 조사할지 결정
2. 필요한 정보를 수집
3. 교차 검증
4. 리포트 생성
"""

import json
import logging
from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from .config import agent_settings
from .graph import (
    CollectedItem,
    InvestigationReport,
    InvestigationState,
    VerifiedFact,
)
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


class InvestigationAgent:
    """
    자율 조사 에이전트

    사건이 트리거되면:
    1. PLANNER: 조사 계획 수립 (어떤 질문에 답해야 하는지, 어떤 소스를 볼지)
    2. EXECUTOR: 도구를 사용하여 정보 수집 (에이전트가 스스로 도구 선택)
    3. VERIFIER: 수집된 정보 교차 검증
    4. PUBLISHER: 최종 리포트 생성
    """

    def __init__(self):
        # LLM (저렴한 모델) - 도구 바인딩 버전 (executor용)
        self.llm = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=agent_settings.llm_temperature,
            api_key=agent_settings.openai_api_key,
        ).bind_tools(ALL_TOOLS)

        # LLM (도구 없음) - 검증/발행용
        self.llm_no_tools = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=agent_settings.llm_temperature,
            api_key=agent_settings.openai_api_key,
        )

        # 그래프 구성
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """LangGraph 상태 머신 구성"""

        # 상태 정의 (메시지 누적)
        class AgentState(InvestigationState):
            messages: Annotated[list, add_messages]

        graph = StateGraph(AgentState)

        # 노드 추가
        graph.add_node("planner", self._plan_node)
        graph.add_node("executor", self._execute_node)
        graph.add_node("tools", ToolNode(ALL_TOOLS))
        graph.add_node("verifier", self._verify_node)
        graph.add_node("publisher", self._publish_node)

        # 엣지 연결
        graph.set_entry_point("planner")
        graph.add_edge("planner", "executor")

        # executor → tools 또는 verifier
        graph.add_conditional_edges(
            "executor",
            self._should_use_tools,
            {
                "tools": "tools",
                "verify": "verifier",
            },
        )

        # tools → executor (도구 결과 받아서 계속)
        graph.add_edge("tools", "executor")

        # verifier → publisher 또는 planner (재조사)
        graph.add_conditional_edges(
            "verifier",
            self._should_continue,
            {
                "replan": "planner",
                "publish": "publisher",
            },
        )

        graph.add_edge("publisher", END)

        return graph.compile(checkpointer=MemorySaver())

    async def investigate(self, event: str, category: str) -> InvestigationReport:
        """
        사건 조사 실행

        Args:
            event: 사건 설명 (예: "Large protests reported in Tehran, Iran")
            category: 카테고리 (war, protest, terrorism 등)

        Returns:
            조사 리포트
        """
        logger.info(f"Starting investigation: {event}")

        initial_state = {
            "event": event,
            "event_category": category,
            "plan": None,
            "collected_items": [],
            "verified_facts": [],
            "iteration": 0,
            "tool_calls_count": 0,
            "messages": [],
            "report": None,
            "status": "planning",
        }

        config = {
            "configurable": {"thread_id": f"inv_{datetime.utcnow().isoformat()}"},
            "recursion_limit": 50,  # 기본 25에서 증가
        }

        # 그래프 실행
        final_state = await self.graph.ainvoke(initial_state, config)

        if final_state.get("report"):
            return InvestigationReport(**final_state["report"])
        else:
            # 실패 시 기본 리포트
            return InvestigationReport(
                event_summary=f"Investigation incomplete for: {event}",
                category=category,
                timeline=[],
                verified_facts=[],
                media=[],
                sources=[],
                unverified_claims=[],
            )

    # ============================================================
    # 노드 함수들
    # ============================================================

    async def _plan_node(self, state: dict) -> dict:
        """
        PLANNER: 조사 계획 수립

        에이전트가 스스로 결정:
        - 어떤 질문에 답해야 하는지
        - 어떤 소스를 확인해야 하는지
        """
        event = state["event"]
        category = state["event_category"]
        iteration = state.get("iteration", 0)

        # 이전 수집 결과 요약 (재조사 시)
        previous_summary = ""
        if state.get("collected_items"):
            previous_summary = f"\n\nPrevious findings ({len(state['collected_items'])} items collected):\n"
            for item in state["collected_items"][:5]:
                previous_summary += f"- [{item.get('source_name')}] {item.get('title', item.get('content', '')[:100])}\n"

        system_prompt = f"""You are an investigative journalist researching breaking news events.

EVENT: {event}
CATEGORY: {category}
ITERATION: {iteration + 1}/3
{previous_summary}

Your task is to create an investigation plan. Consider:
1. What are the KEY QUESTIONS that need to be answered?
2. What SOURCES should be checked? Think about:
   - News agencies (Reuters, BBC, Al Jazeera)
   - Regional specialists (Iran International for Iran, Kyiv Independent for Ukraine)
   - Social media (Telegram channels for real-time footage)
   - RSS feeds for latest headlines

Respond with a plan in this format:
QUESTIONS:
1. [First question]
2. [Second question]
...

SOURCES:
- [Source 1 and why]
- [Source 2 and why]
...

SEARCH_STRATEGY:
[Brief description of how to search - what keywords, in what order]"""

        response = await self.llm_no_tools.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Create investigation plan for: {event}"),
            ]
        )

        # 계획 파싱 및 저장
        plan = self._parse_plan(response.content)

        return {
            **state,
            "plan": plan,
            "iteration": iteration + 1,
            "status": "collecting",
            "messages": [response],
        }

    async def _execute_node(self, state: dict) -> dict:
        """
        EXECUTOR: 도구를 사용하여 정보 수집

        에이전트가 도구를 자율적으로 선택하여 사용
        """
        plan = state.get("plan", {})
        event = state["event"]
        collected = state.get("collected_items", [])
        tool_calls_count = state.get("tool_calls_count", 0)

        # 이전 메시지에서 도구 결과가 있으면 카운트 증가
        messages = state.get("messages", [])
        if messages:
            for msg in messages[-3:]:  # 최근 3개 메시지만 확인
                if hasattr(msg, "type") and msg.type == "tool":
                    tool_calls_count += 1
                    break

        # 수집 충분한지 체크 (10개 이상 또는 도구 호출 5회 이상)
        if len(collected) >= 10 or tool_calls_count >= 5:
            logger.info(f"Collection complete: {len(collected)} items, {tool_calls_count} tool calls")
            return {**state, "status": "verifying", "tool_calls_count": tool_calls_count}

        system_prompt = f"""You are collecting information about: {event}

Investigation plan:
{json.dumps(plan, indent=2, default=str)}

Already collected {len(collected)} items.

Use the available tools to gather more information:
- search_web: For general news search
- search_news_gdelt: For latest news from 100,000+ global sources
- search_telegram: For real-time footage and local reports
- get_video_info: To get details about video URLs
- translate_text: To translate non-English content

Choose the most appropriate tool based on the plan. Focus on getting diverse sources.
If you have enough information (10+ items from multiple sources), say "COLLECTION_COMPLETE"."""

        messages = state.get("messages", [])
        messages.append(SystemMessage(content=system_prompt))

        response = await self.llm.ainvoke(messages)

        # 디버깅: LLM 응답 확인
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tools_called = [t['name'] for t in response.tool_calls]
            print(f"[EXECUTOR] Calling tools: {', '.join(tools_called)}")

        return {
            **state,
            "messages": [*messages, response],
            "tool_calls_count": tool_calls_count,
        }

    def _should_use_tools(self, state: dict) -> Literal["tools", "verify"]:
        """도구 사용 여부 결정"""
        messages = state.get("messages", [])
        tool_calls_count = state.get("tool_calls_count", 0)


        # 도구 호출 횟수 제한 (5회)
        if tool_calls_count >= 5:
            print(f"[EXECUTOR] Tool limit reached, moving to verification")
            return "verify"

        if not messages:
            return "verify"

        last_message = messages[-1]

        # 도구 호출이 있으면 tools로 (카운트 증가는 tools 노드에서)
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # COLLECTION_COMPLETE이면 검증으로
        if hasattr(last_message, "content") and "COLLECTION_COMPLETE" in str(
            last_message.content
        ):
            return "verify"

        # 수집된 데이터가 충분하면 검증으로
        if len(state.get("collected_items", [])) >= 10:
            return "verify"

        # 그 외에는 verify로 (무한 루프 방지)
        return "verify"

    async def _verify_node(self, state: dict) -> dict:
        """
        VERIFIER: 수집된 정보 교차 검증

        최소 2개 독립 소스에서 확인된 정보만 검증됨으로 표시
        """
        collected = state.get("collected_items", [])
        event = state["event"]

        # 메시지에서 도구 결과 추출하여 collected_items 업데이트
        messages = state.get("messages", [])
        print(f"[VERIFIER] Processing {len(messages)} messages...")

        collected = self._extract_tool_results(messages)
        print(f"[VERIFIER] Extracted {len(collected)} items from tools")

        if not collected:
            print(f"[VERIFIER] No data collected, skipping verification")
            return {**state, "verified_facts": [], "status": "done"}

        # 수집된 정보 요약
        collected_summary = "\n".join(
            [
                f"- [{item.get('source_name', 'unknown')}] {item.get('title', '')}: {item.get('content', '')[:200]}"
                for item in collected[:20]
            ]
        )

        system_prompt = f"""You are fact-checking information about: {event}

Collected information:
{collected_summary}

Your task:
1. Identify CLAIMS that appear in the collected information
2. For each claim, check if it's supported by 2+ INDEPENDENT sources
3. Flag any CONFLICTING information

Respond in this format:
VERIFIED_FACTS:
- CLAIM: [claim text]
  SOURCES: [source1, source2, ...]
  CONFIDENCE: [high/medium/low]

UNVERIFIED_CLAIMS:
- [claim that couldn't be verified]

CONFLICTS:
- [any conflicting information found]"""

        response = await self.llm_no_tools.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content="Verify the collected information"),
            ]
        )

        verified_facts = self._parse_verification(response.content)
        print(f"[VERIFIER] Found {len(verified_facts)} verified facts")

        return {
            **state,
            "collected_items": collected,
            "verified_facts": verified_facts,
            "status": "publishing" if verified_facts else "replanning",
            "messages": [*state.get("messages", []), response],
        }

    def _should_continue(self, state: dict) -> Literal["replan", "publish"]:
        """재조사 필요 여부 결정"""
        verified = state.get("verified_facts", [])
        iteration = state.get("iteration", 0)

        # 최대 반복 횟수 도달
        if iteration >= agent_settings.max_investigation_iterations:
            return "publish"

        # 검증된 사실이 있으면 발행
        if verified:
            return "publish"

        # 없으면 재조사 (최대 반복까지)
        return "replan"

    async def _publish_node(self, state: dict) -> dict:
        """
        PUBLISHER: 최종 리포트 생성
        """
        event = state["event"]
        category = state["event_category"]
        verified_facts = state.get("verified_facts", [])
        collected = state.get("collected_items", [])

        # 미디어 URL 추출
        media_urls = []
        for item in collected:
            if item.get("media_urls"):
                media_urls.extend(item["media_urls"])
            if item.get("source_type") == "video":
                media_urls.append(item.get("url", ""))

        # 소스 목록
        sources = list(set(item.get("source_name", "") for item in collected))

        system_prompt = f"""Create a comprehensive news report about: {event}

Verified facts:
{json.dumps(verified_facts, indent=2, default=str)}

Sources used: {', '.join(sources)}

Create a professional news report with:
1. SUMMARY: 2-3 sentence overview
2. TIMELINE: Key events in chronological order
3. DETAILS: Expanded information from verified facts
4. UNVERIFIED: Any claims that couldn't be verified (clearly labeled)

Keep it factual and cite sources."""

        response = await self.llm_no_tools.ainvoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content="Generate the final report"),
            ]
        )

        print(f"[PUBLISHER] Generating final report...")

        # 리포트 구성
        report = {
            "event_summary": self._extract_summary(response.content),
            "category": category,
            "location": self._extract_location(event),
            "timeline": self._extract_timeline(response.content),
            "verified_facts": verified_facts,
            "media": media_urls[:10],  # 최대 10개
            "sources": sources,
            "unverified_claims": self._extract_unverified(response.content),
            "generated_at": datetime.utcnow().isoformat(),
        }

        return {
            **state,
            "report": report,
            "status": "done",
        }

    # ============================================================
    # 헬퍼 함수들
    # ============================================================

    def _parse_plan(self, content: str) -> dict:
        """계획 파싱"""
        plan = {"questions": [], "sources": [], "strategy": ""}

        lines = content.split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if "QUESTIONS:" in line.upper():
                current_section = "questions"
            elif "SOURCES:" in line.upper():
                current_section = "sources"
            elif "SEARCH_STRATEGY:" in line.upper():
                current_section = "strategy"
            elif line and current_section:
                if line.startswith(("-", "•", "*")) or line[0].isdigit():
                    clean = line.lstrip("-•* 0123456789.")
                    if current_section == "questions":
                        plan["questions"].append(clean)
                    elif current_section == "sources":
                        plan["sources"].append(clean)
                elif current_section == "strategy":
                    plan["strategy"] += line + " "

        return plan

    def _parse_verification(self, content: str) -> list[dict]:
        """검증 결과 파싱"""
        facts = []
        current_fact = {}

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("- CLAIM:") or line.startswith("CLAIM:"):
                if current_fact:
                    facts.append(current_fact)
                current_fact = {"claim": line.split(":", 1)[1].strip()}

            elif "SOURCES:" in line.upper() and current_fact:
                sources_text = line.split(":", 1)[1].strip()
                current_fact["supporting_sources"] = [
                    s.strip() for s in sources_text.split(",")
                ]

            elif "CONFIDENCE:" in line.upper() and current_fact:
                conf_text = line.split(":", 1)[1].strip().lower()
                conf_map = {"high": 0.9, "medium": 0.7, "low": 0.5}
                current_fact["confidence"] = conf_map.get(conf_text, 0.6)

        if current_fact and "claim" in current_fact:
            facts.append(current_fact)

        return facts

    def _extract_tool_results(self, messages: list) -> list[dict]:
        """메시지에서 도구 결과 추출"""
        from langchain_core.messages import ToolMessage

        results = []
        for msg in messages:
            # ToolMessage 타입 체크 (LangGraph ToolNode 결과)
            if isinstance(msg, ToolMessage):
                content = msg.content

                # content가 이미 리스트/딕트인 경우
                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict):
                            # source 정보 추가
                            item["source_name"] = item.get("source_name", msg.name or "unknown")
                            results.append(item)
                elif isinstance(content, dict):
                    content["source_name"] = content.get("source_name", msg.name or "unknown")
                    results.append(content)
                elif isinstance(content, str):
                    # JSON 문자열인 경우 파싱
                    try:
                        if content.startswith("[") or content.startswith("{"):
                            data = json.loads(content)
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict):
                                        item["source_name"] = item.get("source_name", msg.name or "unknown")
                                        results.append(item)
                            elif isinstance(data, dict):
                                data["source_name"] = data.get("source_name", msg.name or "unknown")
                                results.append(data)
                    except json.JSONDecodeError:
                        # JSON이 아닌 텍스트 결과
                        if content and len(content) > 10:
                            results.append({
                                "source_name": msg.name or "unknown",
                                "content": content,
                                "title": f"Result from {msg.name}",
                            })
            # 일반 메시지에서도 JSON 체크 (fallback)
            elif hasattr(msg, "content") and isinstance(msg.content, str):
                try:
                    if msg.content.startswith("[") or msg.content.startswith("{"):
                        data = json.loads(msg.content)
                        if isinstance(data, list):
                            results.extend(data)
                        elif isinstance(data, dict):
                            results.append(data)
                except:
                    pass

        return results

    def _extract_summary(self, content: str) -> str:
        """요약 추출"""
        lines = content.split("\n")
        in_summary = False
        summary_lines = []

        for line in lines:
            # SUMMARY 섹션 시작 체크 (마크다운 포함)
            if "SUMMARY" in line.upper():
                in_summary = True
                # 같은 줄에 내용이 있으면 추출
                parts = line.split(":", 1)
                if len(parts) > 1:
                    text = parts[1].strip().strip("*").strip()
                    if text:
                        summary_lines.append(text)
                continue

            if in_summary:
                # 다음 섹션 시작하면 종료
                if any(section in line.upper() for section in ["TIMELINE:", "DETAILS:", "UNVERIFIED:"]):
                    break
                # 빈 줄이면 종료
                if not line.strip():
                    break
                # 마크다운 볼드 제거
                clean_line = line.strip().strip("*").strip()
                if clean_line:
                    summary_lines.append(clean_line)

        if summary_lines:
            return " ".join(summary_lines)[:500]

        # fallback: 첫 문단 반환
        paragraphs = content.split("\n\n")
        return paragraphs[0].strip("*").strip()[:500] if paragraphs else ""

    def _extract_location(self, event: str) -> str | None:
        """위치 추출 (간단한 규칙 기반)"""
        # 일반적인 위치 패턴
        import re

        patterns = [
            r"in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",  # "in Tehran"
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:protests?|conflict|war|attack)",
        ]
        for pattern in patterns:
            match = re.search(pattern, event)
            if match:
                return match.group(1)
        return None

    def _extract_timeline(self, content: str) -> list[str]:
        """타임라인 추출"""
        timeline = []
        in_timeline = False

        for line in content.split("\n"):
            if "TIMELINE:" in line.upper():
                in_timeline = True
                continue
            if in_timeline:
                if line.strip().startswith(("-", "•", "*")) or (
                    line.strip() and line.strip()[0].isdigit()
                ):
                    timeline.append(line.strip().lstrip("-•* 0123456789."))
                elif line.strip() and not line.strip().startswith(
                    ("SUMMARY", "DETAILS", "UNVERIFIED")
                ):
                    continue
                else:
                    in_timeline = False

        return timeline

    def _extract_unverified(self, content: str) -> list[str]:
        """미검증 클레임 추출"""
        unverified = []
        in_unverified = False

        for line in content.split("\n"):
            if "UNVERIFIED:" in line.upper():
                in_unverified = True
                continue
            if in_unverified:
                if line.strip().startswith(("-", "•", "*")):
                    unverified.append(line.strip().lstrip("-•* "))
                elif not line.strip():
                    in_unverified = False

        return unverified


async def test_investigation():
    """테스트용: 조사 에이전트 실행"""
    agent = InvestigationAgent()

    # 테스트 사건
    report = await agent.investigate(
        event="Large protests reported in Tehran, Iran against government",
        category="protest",
    )

    print("\n" + "=" * 60)
    print("📋 INVESTIGATION REPORT")
    print("=" * 60)
    print(f"\n📝 Summary: {report.event_summary}")
    print(f"📍 Location: {report.location}")
    print(f"🏷️ Category: {report.category}")
    print(f"\n⏱️ Timeline:")
    for item in report.timeline:
        print(f"  - {item}")
    print(f"\n✅ Verified Facts ({len(report.verified_facts)}):")
    for fact in report.verified_facts:
        print(f"  - {fact.get('claim', fact)}")
    print(f"\n⚠️ Unverified Claims:")
    for claim in report.unverified_claims:
        print(f"  - {claim}")
    print(f"\n📰 Sources: {', '.join(report.sources)}")
    print(f"\n🎬 Media: {len(report.media)} items")

    return report


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_investigation())
