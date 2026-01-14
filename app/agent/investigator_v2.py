"""
Deep Verification Investigation Agent (Production-Ready)

Based on Perplexity Deep Research + GPT-Researcher best practices:
1. Query Decomposition - Split topic into subtopics
2. Parallel Multi-pass Retrieval - Search subtopics concurrently with ReAct pattern
3. Structured Notes - Intermediate synthesis per topic
4. Conflict Detection - Find and flag contradictions
5. Confidence Scoring - Per source and per claim
6. Final Synthesis - Combine with citations and uncertainty notes

Production Features:
- Rate limiting with asyncio.Semaphore
- Retry with exponential backoff (tenacity)
- Request timeouts
- Parallel subtopic research
- Structured logging
- Source deduplication
- Proper error handling
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal
from urllib.parse import urlparse

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
)

from .config import agent_settings
from .graph import InvestigationReport, InvestigationState
from .tools import ALL_TOOLS

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

class AgentConfig:
    """Production configuration for the agent"""

    # ReAct pattern limits
    MAX_REACT_ITERATIONS: int = 3
    MIN_SOURCES_PER_SUBTOPIC: int = 5
    MAX_SUBTOPICS: int = 5

    # Rate limiting
    MAX_CONCURRENT_SEARCHES: int = 5
    MAX_CONCURRENT_LLM_CALLS: int = 3

    # Timeouts (seconds)
    TOOL_TIMEOUT: float = 30.0
    LLM_TIMEOUT: float = 60.0

    # Retry settings
    MAX_RETRIES: int = 3
    RETRY_MIN_WAIT: float = 1.0
    RETRY_MAX_WAIT: float = 10.0


# =============================================================================
# Data Models
# =============================================================================

class SourceItem(BaseModel):
    """Individual source with metadata and deduplication"""

    url: str
    title: str = ""
    content: str = ""
    source_name: str = "unknown"
    published: str | None = None
    credibility: float = Field(default=0.5, ge=0.0, le=1.0)

    @property
    def url_hash(self) -> str:
        """Generate hash for deduplication"""
        normalized = self._normalize_url(self.url)
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """Normalize URL for deduplication"""
        parsed = urlparse(url.lower().strip())
        # Remove trailing slashes, www prefix, query params for dedup
        netloc = parsed.netloc.replace("www.", "")
        path = parsed.path.rstrip("/")
        return f"{netloc}{path}"


class StructuredNote(BaseModel):
    """Intermediate note for a subtopic"""

    subtopic: str
    findings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class VerifiedClaim(BaseModel):
    """Verified claim with evidence"""

    claim: str
    supporting_sources: list[str] = Field(default_factory=list)
    conflicting_sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    is_disputed: bool = False
    notes: str | None = None


class SubtopicResult(BaseModel):
    """Result from researching a single subtopic"""

    subtopic: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    note: StructuredNote | None = None
    error: str | None = None


class DeepVerificationState(InvestigationState):
    """Extended state for deep verification"""

    subtopics: list[str] = Field(default_factory=list)
    subtopic_results: list[dict[str, Any]] = Field(default_factory=list)
    structured_notes: list[dict[str, Any]] = Field(default_factory=list)
    source_items: list[dict[str, Any]] = Field(default_factory=list)
    conflicts_detected: list[dict[str, Any]] = Field(default_factory=list)
    seen_url_hashes: set[str] = Field(default_factory=set)


# =============================================================================
# Tool Utilities
# =============================================================================

TOOL_MAP: dict[str, BaseTool] = {tool.name: tool for tool in ALL_TOOLS}


async def execute_tool_with_retry(
    tool: BaseTool,
    args: dict[str, Any],
    config: AgentConfig,
    semaphore: asyncio.Semaphore,
) -> dict[str, Any] | list[dict[str, Any]] | str:
    """Execute a tool with retry logic and rate limiting"""
    async with semaphore:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(config.MAX_RETRIES),
                wait=wait_exponential(
                    multiplier=config.RETRY_MIN_WAIT,
                    max=config.RETRY_MAX_WAIT,
                ),
                reraise=True,
            ):
                with attempt:
                    result = await asyncio.wait_for(
                        tool.ainvoke(args),
                        timeout=config.TOOL_TIMEOUT,
                    )
                    return result
        except asyncio.TimeoutError:
            logger.warning(
                "Tool timeout",
                extra={"tool": tool.name, "timeout": config.TOOL_TIMEOUT},
            )
            return {"error": f"Timeout after {config.TOOL_TIMEOUT}s"}
        except RetryError as e:
            logger.error(
                "Tool failed after retries",
                extra={"tool": tool.name, "attempts": config.MAX_RETRIES, "error": str(e)},
            )
            return {"error": f"Failed after {config.MAX_RETRIES} retries: {e}"}
        except Exception as e:
            logger.error(
                "Tool execution error",
                extra={"tool": tool.name, "error": str(e), "error_type": type(e).__name__},
            )
            return {"error": f"{type(e).__name__}: {e}"}


# =============================================================================
# Deep Verification Agent
# =============================================================================

class DeepVerificationAgent:
    """
    Production-Ready Deep Verification Agent

    Pipeline:
    1. DECOMPOSER: Split query into subtopics
    2. PARALLEL_RESEARCHER: Research all subtopics concurrently with ReAct
    3. VERIFIER: Cross-verify and detect conflicts
    4. SYNTHESIZER: Generate final report with citations

    Features:
    - Rate limiting with asyncio.Semaphore
    - Retry with exponential backoff
    - Parallel subtopic research
    - Structured logging
    - Source deduplication
    """

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()

        # Semaphores for rate limiting
        self._search_semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_SEARCHES)
        self._llm_semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_LLM_CALLS)

        # LLM with tools bound for autonomous selection
        self.llm = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=0.1,
            api_key=agent_settings.openai_api_key,
        ).bind_tools(ALL_TOOLS)

        # LLM without tools for synthesis/verification
        self.llm_no_tools = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=0.1,
            api_key=agent_settings.openai_api_key,
        )

        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the deep verification graph"""
        graph = StateGraph(DeepVerificationState)

        # Nodes
        graph.add_node("decomposer", self._decompose_node)
        graph.add_node("parallel_researcher", self._parallel_research_node)
        graph.add_node("verifier", self._verify_node)
        graph.add_node("synthesizer", self._synthesize_node)

        # Flow: Linear pipeline (parallel research happens within the node)
        graph.set_entry_point("decomposer")
        graph.add_edge("decomposer", "parallel_researcher")
        graph.add_edge("parallel_researcher", "verifier")
        graph.add_edge("verifier", "synthesizer")
        graph.add_edge("synthesizer", END)

        return graph.compile(checkpointer=MemorySaver())

    async def investigate(self, event: str, category: str) -> InvestigationReport:
        """Run deep verification investigation"""
        logger.info(
            "Starting investigation",
            extra={"event": event[:100], "category": category},
        )

        initial_state = {
            "event": event,
            "event_category": category,
            "subtopics": [],
            "subtopic_results": [],
            "structured_notes": [],
            "source_items": [],
            "conflicts_detected": [],
            "seen_url_hashes": set(),
            "collected_items": [],
            "verified_facts": [],
            "iteration": 0,
            "tool_calls_count": 0,
            "messages": [],
            "plan": None,
            "report": None,
            "status": "decomposing",
        }

        config = {
            "configurable": {"thread_id": f"deep_{datetime.utcnow().isoformat()}"},
            "recursion_limit": 50,
        }

        try:
            final_state = await self.graph.ainvoke(initial_state, config)

            if final_state.get("report"):
                return InvestigationReport(**final_state["report"])
        except Exception as e:
            logger.error(
                "Investigation failed",
                extra={"error": str(e), "error_type": type(e).__name__},
            )

        return InvestigationReport(
            event_summary=f"Investigation incomplete: {event}",
            category=category,
            timeline=[],
            verified_facts=[],
            media=[],
            sources=[],
            unverified_claims=[],
        )

    # =========================================================================
    # Node Implementations
    # =========================================================================

    async def _decompose_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        DECOMPOSER: Split main query into 3-5 subtopics
        """
        event = state["event"]
        category = state["event_category"]

        logger.info("Decomposing query", extra={"event": event[:50]})

        prompt = f"""You are a research analyst decomposing a breaking news event into key subtopics.

EVENT: {event}
CATEGORY: {category}

Break this into 3-5 specific subtopics that need independent research.
Each subtopic should answer a different aspect:
- What happened? (facts, timeline)
- Who is involved? (actors, victims)
- Where exactly? (locations, geography)
- Why/causes? (background, triggers)
- Impact/response? (casualties, reactions)

Respond with ONLY the subtopics, one per line:
SUBTOPIC: [specific research question]
SUBTOPIC: [specific research question]
..."""

        try:
            response = await asyncio.wait_for(
                self.llm_no_tools.ainvoke([
                    SystemMessage(content=prompt),
                    HumanMessage(content=f"Decompose: {event}"),
                ]),
                timeout=self.config.LLM_TIMEOUT,
            )
            subtopics = self._parse_subtopics(response.content)
        except asyncio.TimeoutError:
            logger.warning("Decomposer timeout, using default subtopics")
            subtopics = self._get_default_subtopics()
        except Exception as e:
            logger.error(f"Decomposer error: {e}")
            subtopics = self._get_default_subtopics()

        logger.info(
            "Decomposition complete",
            extra={"subtopic_count": len(subtopics)},
        )

        return {
            **state,
            "subtopics": subtopics,
            "status": "researching",
        }

    async def _parallel_research_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        PARALLEL_RESEARCHER: Research all subtopics concurrently

        Each subtopic runs the ReAct pattern independently.
        Results are aggregated with deduplication.
        """
        subtopics = state.get("subtopics", [])
        event = state["event"]

        if not subtopics:
            return {**state, "status": "verifying"}

        logger.info(
            "Starting parallel research",
            extra={"subtopic_count": len(subtopics)},
        )

        # Research all subtopics in parallel
        tasks = [
            self._research_subtopic(event, subtopic, idx, len(subtopics))
            for idx, subtopic in enumerate(subtopics)
        ]

        results: list[SubtopicResult] = await asyncio.gather(
            *tasks, return_exceptions=True
        )

        # Process results
        all_sources: list[dict[str, Any]] = []
        structured_notes: list[dict[str, Any]] = []
        seen_hashes: set[str] = set()
        total_sources = 0

        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Subtopic research failed: {result}")
                continue

            if isinstance(result, SubtopicResult):
                # Deduplicate sources
                for source in result.sources:
                    if isinstance(source, dict) and source.get("url"):
                        source_item = SourceItem(
                            url=source.get("url", ""),
                            title=source.get("title", ""),
                            content=source.get("content", ""),
                            source_name=source.get("source_name", "unknown"),
                        )
                        if source_item.url_hash not in seen_hashes:
                            seen_hashes.add(source_item.url_hash)
                            all_sources.append(source)
                            total_sources += 1

                # Add note if exists
                if result.note:
                    structured_notes.append(result.note.model_dump())

        logger.info(
            "Parallel research complete",
            extra={
                "total_sources": total_sources,
                "unique_sources": len(seen_hashes),
                "notes_created": len(structured_notes),
            },
        )

        return {
            **state,
            "source_items": all_sources,
            "structured_notes": structured_notes,
            "seen_url_hashes": seen_hashes,
            "status": "verifying",
        }

    async def _research_subtopic(
        self,
        event: str,
        subtopic: str,
        idx: int,
        total: int,
    ) -> SubtopicResult:
        """
        Research a single subtopic using ReAct pattern

        Returns SubtopicResult with sources and structured note.
        """
        logger.info(
            f"Researching subtopic {idx + 1}/{total}",
            extra={"subtopic": subtopic[:50]},
        )

        messages: list[BaseMessage] = [
            SystemMessage(content=f"""You are researching a specific aspect of a news event.

MAIN EVENT: {event}
CURRENT SUBTOPIC: {subtopic}

Search for information about this specific subtopic using available tools.
You have access to these search tools:
- search_news_gdelt: FREE - For news articles (prefer this first)
- search_web_free: FREE - For general web search via DuckDuckGo
- search_web: PAID - High-quality Tavily search (use as fallback)
- search_telegram: For real-time social media
- search_youtube: For video content

Strategy:
1. Start with FREE tools (GDELT, DuckDuckGo)
2. Use paid tools only if free tools don't provide enough info
3. Stop when you have sufficient information (5+ sources)

Focus on finding:
- Specific facts and numbers
- Named sources and officials
- Dates and timeline
- Multiple perspectives"""),
            HumanMessage(content=f"Search for information about: {subtopic}"),
        ]

        all_sources: list[dict[str, Any]] = []

        # ReAct loop
        for iteration in range(self.config.MAX_REACT_ITERATIONS):
            try:
                # Get LLM response with timeout
                async with self._llm_semaphore:
                    response = await asyncio.wait_for(
                        self.llm.ainvoke(messages),
                        timeout=self.config.LLM_TIMEOUT,
                    )
                messages.append(response)

                # Check if LLM wants to call tools
                if not response.tool_calls:
                    logger.debug(
                        f"Subtopic {idx + 1}: LLM finished at iteration {iteration + 1}"
                    )
                    break

                # Execute tool calls
                tool_names = [tc["name"] for tc in response.tool_calls]
                logger.debug(
                    f"Subtopic {idx + 1}: Iteration {iteration + 1}, tools: {tool_names}"
                )

                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["args"]
                    tool_id = tool_call["id"]

                    tool = TOOL_MAP.get(tool_name)
                    if not tool:
                        messages.append(
                            ToolMessage(
                                content=f"Tool {tool_name} not found",
                                tool_call_id=tool_id,
                            )
                        )
                        continue

                    # Execute with retry and rate limiting
                    result = await execute_tool_with_retry(
                        tool, tool_args, self.config, self._search_semaphore
                    )

                    # Process results
                    result_str = self._process_tool_result(
                        result, tool_name, all_sources
                    )

                    messages.append(
                        ToolMessage(content=result_str, tool_call_id=tool_id)
                    )

            except asyncio.TimeoutError:
                logger.warning(f"Subtopic {idx + 1}: LLM timeout at iteration {iteration + 1}")
                break
            except Exception as e:
                logger.error(f"Subtopic {idx + 1}: Error at iteration {iteration + 1}: {e}")
                break

        # Create structured note
        note = await self._create_note(subtopic, all_sources)

        logger.info(
            f"Subtopic {idx + 1}/{total} complete",
            extra={"sources": len(all_sources)},
        )

        return SubtopicResult(
            subtopic=subtopic,
            sources=all_sources,
            note=note,
        )

    def _process_tool_result(
        self,
        result: Any,
        tool_name: str,
        all_sources: list[dict[str, Any]],
    ) -> str:
        """Process tool result and add to sources"""
        if isinstance(result, list):
            count = 0
            for item in result:
                if isinstance(item, dict) and not item.get("error"):
                    item["source_name"] = item.get("source_name", tool_name)
                    all_sources.append(item)
                    count += 1
            return f"Found {count} results"

        if isinstance(result, dict):
            if result.get("error"):
                return f"Error: {result['error']}"
            result["source_name"] = result.get("source_name", tool_name)
            all_sources.append(result)
            return "Found 1 result"

        return str(result)[:500]

    async def _create_note(
        self,
        subtopic: str,
        sources: list[dict[str, Any]],
    ) -> StructuredNote:
        """Create structured note for a subtopic"""
        if not sources:
            return StructuredNote(
                subtopic=subtopic,
                findings=["No information found"],
                confidence=0.0,
            )

        sources_text = "\n".join([
            f"- [{s.get('source_name', 'unknown')}] {s.get('title', '')}: {s.get('content', '')[:200]}"
            for s in sources[:15]
            if isinstance(s, dict)
        ])

        prompt = f"""Analyze the search results for this subtopic.

SUBTOPIC: {subtopic}

SOURCES:
{sources_text}

Extract:
1. KEY FINDINGS: Main facts discovered (be specific with numbers, names, dates)
2. CONFLICTS: Any contradicting information between sources
3. CONFIDENCE: How confident are you in these findings? (high/medium/low)

Format:
FINDING: [specific fact with source]
FINDING: [specific fact with source]
CONFLICT: [if any contradiction found]
CONFIDENCE: [high/medium/low]"""

        try:
            async with self._llm_semaphore:
                response = await asyncio.wait_for(
                    self.llm_no_tools.ainvoke([
                        SystemMessage(content=prompt),
                        HumanMessage(content="Analyze and create notes"),
                    ]),
                    timeout=self.config.LLM_TIMEOUT,
                )
            return self._parse_note(response.content, subtopic, sources)
        except Exception as e:
            logger.error(f"Note creation failed: {e}")
            return StructuredNote(
                subtopic=subtopic,
                findings=[f"Analysis failed: {e}"],
                sources=[s.get("source_name", "unknown") for s in sources[:5]],
                confidence=0.3,
            )

    async def _verify_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        VERIFIER: Cross-verify facts and detect conflicts
        """
        notes = state.get("structured_notes", [])
        source_items = state.get("source_items", [])
        event = state["event"]

        logger.info(
            "Cross-verifying facts",
            extra={"notes_count": len(notes), "sources_count": len(source_items)},
        )

        # Compile all findings
        all_findings: list[str] = []
        all_conflicts: list[str] = []

        for note in notes:
            if isinstance(note, dict):
                all_findings.extend(note.get("findings", []))
                all_conflicts.extend(note.get("conflicts", []))

        findings_text = "\n".join([f"- {f}" for f in all_findings[:30]])
        conflicts_text = (
            "\n".join([f"- {c}" for c in all_conflicts])
            if all_conflicts
            else "None detected"
        )

        prompt = f"""You are a fact-checker performing deep verification.

EVENT: {event}

ALL FINDINGS FROM RESEARCH:
{findings_text}

CONFLICTS DETECTED:
{conflicts_text}

TOTAL SOURCES: {len(source_items)}

Perform verification:
1. Identify claims that appear in 2+ independent sources -> VERIFIED
2. Identify claims with only 1 source -> UNVERIFIED
3. Identify contradicting claims -> DISPUTED
4. Assign confidence score to each claim

Format each verified claim as:
VERIFIED: [claim]
SOURCES: [list of sources]
CONFIDENCE: [0.0-1.0]
DISPUTED: [yes/no]
NOTE: [any important context]

UNVERIFIED: [claim with single source]

DISPUTED: [contradicting claims with explanation]"""

        try:
            async with self._llm_semaphore:
                response = await asyncio.wait_for(
                    self.llm_no_tools.ainvoke([
                        SystemMessage(content=prompt),
                        HumanMessage(content="Perform deep verification"),
                    ]),
                    timeout=self.config.LLM_TIMEOUT,
                )
            verified_facts, unverified, conflicts = self._parse_verification(
                response.content
            )
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            verified_facts, unverified, conflicts = [], [], []

        logger.info(
            "Verification complete",
            extra={
                "verified": len(verified_facts),
                "unverified": len(unverified),
                "disputed": len(conflicts),
            },
        )

        return {
            **state,
            "verified_facts": verified_facts,
            "unverified_claims": unverified,
            "conflicts_detected": conflicts,
            "status": "synthesizing",
        }

    async def _synthesize_node(self, state: dict[str, Any]) -> dict[str, Any]:
        """
        SYNTHESIZER: Generate final report with citations
        """
        event = state["event"]
        category = state["event_category"]
        verified_facts = state.get("verified_facts", [])
        unverified = state.get("unverified_claims", [])
        conflicts = state.get("conflicts_detected", [])
        source_items = state.get("source_items", [])

        logger.info("Generating final report")

        import json
        facts_text = json.dumps(verified_facts, indent=2, default=str)

        prompt = f"""Generate a comprehensive news report with citations.

EVENT: {event}
CATEGORY: {category}

VERIFIED FACTS:
{facts_text}

DISPUTED CLAIMS: {len(conflicts)}
UNVERIFIED CLAIMS: {len(unverified)}
TOTAL SOURCES: {len(source_items)}

Create a professional report:

1. SUMMARY: 3-4 sentence overview of the verified facts
2. TIMELINE: Chronological events (only verified, with dates if available)
3. KEY FACTS: Bullet points of most important verified information
4. DISPUTED: Any claims that have conflicting reports (label clearly)
5. UNVERIFIED: Claims from single sources (label as unverified)

IMPORTANT:
- Only include verified information in main body
- Clearly label disputed and unverified claims
- Include source citations
- Note confidence levels where relevant"""

        try:
            async with self._llm_semaphore:
                response = await asyncio.wait_for(
                    self.llm_no_tools.ainvoke([
                        SystemMessage(content=prompt),
                        HumanMessage(content="Generate final report with citations"),
                    ]),
                    timeout=self.config.LLM_TIMEOUT,
                )
            summary = self._extract_summary(response.content)
            timeline = self._extract_timeline(response.content)
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            summary = f"Report generation failed: {e}"
            timeline = []

        # Extract unique source URLs
        sources = list({
            s.get("url") or s.get("source_name", "unknown")
            for s in source_items
            if isinstance(s, dict) and (s.get("url") or s.get("source_name"))
        })

        report = {
            "event_summary": summary,
            "category": category,
            "location": self._extract_location(event),
            "timeline": timeline,
            "verified_facts": verified_facts,
            "media": [],
            "sources": sources[:50],
            "unverified_claims": unverified,
            "disputed_claims": conflicts,
            "confidence_score": self._calculate_overall_confidence(verified_facts),
            "generated_at": datetime.utcnow().isoformat(),
        }

        logger.info(
            "Report complete",
            extra={
                "verified_facts": len(verified_facts),
                "sources": len(sources),
            },
        )

        return {
            **state,
            "report": report,
            "status": "done",
        }

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _parse_subtopics(self, content: str) -> list[str]:
        """Parse subtopics from decomposer output"""
        subtopics: list[str] = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("SUBTOPIC:"):
                subtopics.append(line[9:].strip())
            elif line.startswith("-") or line.startswith("•"):
                subtopics.append(line.lstrip("-• ").strip())

        if len(subtopics) < 3:
            return self._get_default_subtopics()

        return subtopics[: self.config.MAX_SUBTOPICS]

    def _get_default_subtopics(self) -> list[str]:
        """Get default subtopics when decomposition fails"""
        return [
            "What happened? (timeline and facts)",
            "Who is involved? (actors and casualties)",
            "What is the response? (government and international)",
        ]

    def _parse_note(
        self,
        content: str,
        subtopic: str,
        sources: list[dict[str, Any]],
    ) -> StructuredNote:
        """Parse noter output into structured note"""
        findings: list[str] = []
        conflicts: list[str] = []
        confidence = 0.5

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("FINDING:"):
                findings.append(line[8:].strip())
            elif line.startswith("CONFLICT:"):
                conflicts.append(line[9:].strip())
            elif line.startswith("CONFIDENCE:"):
                conf_text = line[11:].strip().lower()
                conf_map = {"high": 0.9, "medium": 0.7, "low": 0.4}
                confidence = conf_map.get(conf_text, 0.5)

        return StructuredNote(
            subtopic=subtopic,
            findings=findings,
            sources=[
                s.get("source_name", "unknown")
                for s in sources[:10]
                if isinstance(s, dict)
            ],
            conflicts=conflicts,
            confidence=confidence,
        )

    def _parse_verification(
        self, content: str
    ) -> tuple[list[dict[str, Any]], list[str], list[str]]:
        """Parse verification output"""
        verified: list[dict[str, Any]] = []
        unverified: list[str] = []
        disputed: list[str] = []

        current: dict[str, Any] | None = None
        current_type: str | None = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("VERIFIED:"):
                if current and current_type == "verified":
                    verified.append(current)
                current = {"claim": line[9:].strip()}
                current_type = "verified"
            elif line.startswith("SOURCES:") and current:
                current["supporting_sources"] = [
                    s.strip() for s in line[8:].split(",")
                ]
            elif line.startswith("CONFIDENCE:") and current:
                try:
                    current["confidence"] = float(line[11:].strip())
                except ValueError:
                    current["confidence"] = 0.7
            elif line.startswith("DISPUTED:") and current:
                current["is_disputed"] = line[9:].strip().lower() == "yes"
            elif line.startswith("NOTE:") and current:
                current["notes"] = line[5:].strip()
            elif line.startswith("UNVERIFIED:"):
                if current and current_type == "verified":
                    verified.append(current)
                unverified.append(line[11:].strip())
                current = None
                current_type = None
            elif line.startswith("DISPUTED:") and not current:
                disputed.append(line[9:].strip())

        if current and current_type == "verified":
            verified.append(current)

        return verified, unverified, disputed

    def _calculate_overall_confidence(
        self, verified_facts: list[dict[str, Any]]
    ) -> float:
        """Calculate overall report confidence"""
        if not verified_facts:
            return 0.0

        scores = [
            f.get("confidence", 0.5)
            for f in verified_facts
            if isinstance(f, dict)
        ]
        return sum(scores) / len(scores) if scores else 0.5

    def _extract_summary(self, content: str) -> str:
        """Extract summary from report"""
        lines = content.split("\n")
        in_summary = False
        summary_lines: list[str] = []

        for line in lines:
            if "SUMMARY" in line.upper():
                in_summary = True
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    summary_lines.append(parts[1].strip())
                continue

            if in_summary:
                if any(
                    s in line.upper()
                    for s in ["TIMELINE:", "KEY FACTS:", "DISPUTED:", "UNVERIFIED:"]
                ):
                    break
                if line.strip():
                    summary_lines.append(line.strip())

        if summary_lines:
            return " ".join(summary_lines)[:600]

        return content.split("\n\n")[0][:600] if content else ""

    def _extract_location(self, event: str) -> str | None:
        """Extract location from event"""
        patterns = [
            r"in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
            r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:protests?|conflict|war|attack)",
        ]
        for pattern in patterns:
            match = re.search(pattern, event)
            if match:
                return match.group(1)
        return None

    def _extract_timeline(self, content: str) -> list[str]:
        """Extract timeline from report"""
        timeline: list[str] = []
        in_timeline = False

        for line in content.split("\n"):
            if "TIMELINE:" in line.upper():
                in_timeline = True
                continue
            if in_timeline:
                stripped = line.strip()
                if stripped.startswith(("-", "•", "*")) or (
                    stripped and stripped[0].isdigit()
                ):
                    timeline.append(stripped.lstrip("-•* 0123456789.").strip())
                elif any(
                    s in line.upper()
                    for s in ["KEY FACTS:", "DISPUTED:", "UNVERIFIED:", "SUMMARY:"]
                ):
                    in_timeline = False

        return timeline


# =============================================================================
# Alias for compatibility
# =============================================================================

InvestigationAgentV2 = DeepVerificationAgent
