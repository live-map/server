"""
Deep Verification Investigation Agent (Perplexity Style)

Based on Perplexity Deep Research architecture:
1. Query Decomposition - Split topic into subtopics
2. Multi-pass Retrieval - Search each subtopic independently
3. Structured Notes - Intermediate synthesis per topic
4. Conflict Detection - Find and flag contradictions
5. Confidence Scoring - Per source and per claim
6. Final Synthesis - Combine with citations and uncertainty notes

Key improvements over v1:
- Deeper fact verification with explicit conflict detection
- Source-level confidence scoring
- Structured intermediate notes before final report
- Better citation tracking throughout pipeline
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Annotated, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

from .config import agent_settings
from .graph import InvestigationReport, InvestigationState
from .tools import ALL_TOOLS

logger = logging.getLogger(__name__)


# =============================================================================
# Data Models for Deep Verification
# =============================================================================


class SourceItem(BaseModel):
    """Individual source with metadata"""
    url: str
    title: str
    content: str
    source_name: str
    published: str | None = None
    credibility: float = 0.5  # 0-1 score


class StructuredNote(BaseModel):
    """Intermediate note for a subtopic"""
    subtopic: str
    findings: list[str] = []
    sources: list[str] = []
    conflicts: list[str] = []
    confidence: float = 0.5


class VerifiedClaim(BaseModel):
    """Verified claim with evidence"""
    claim: str
    supporting_sources: list[str]
    conflicting_sources: list[str] = []
    confidence: float
    is_disputed: bool = False
    notes: str | None = None


class DeepVerificationState(InvestigationState):
    """Extended state for deep verification"""
    subtopics: list[str] = []
    structured_notes: list[dict] = []
    source_items: list[dict] = []
    conflicts_detected: list[dict] = []
    messages: Annotated[list, add_messages] = []


# =============================================================================
# Deep Verification Agent
# =============================================================================


class DeepVerificationAgent:
    """
    Perplexity-style Deep Verification Agent

    Pipeline:
    1. DECOMPOSER: Split query into subtopics
    2. RETRIEVER: Search each subtopic (multi-pass)
    3. NOTER: Create structured notes per subtopic
    4. VERIFIER: Cross-verify and detect conflicts
    5. SYNTHESIZER: Generate final report with citations
    """

    def __init__(self):
        self.llm = ChatOpenAI(
            model=agent_settings.llm_model,
            temperature=0.1,  # Lower for more factual
            api_key=agent_settings.openai_api_key,
        ).bind_tools(ALL_TOOLS)

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
        graph.add_node("retriever", self._retrieve_node)
        graph.add_node("tools", ToolNode(ALL_TOOLS))
        graph.add_node("noter", self._note_node)
        graph.add_node("verifier", self._verify_node)
        graph.add_node("synthesizer", self._synthesize_node)

        # Flow
        graph.set_entry_point("decomposer")
        graph.add_edge("decomposer", "retriever")

        # Retriever -> tools or noter
        graph.add_conditional_edges(
            "retriever",
            self._should_use_tools,
            {"tools": "tools", "note": "noter"}
        )
        graph.add_edge("tools", "retriever")

        # Noter -> verifier or retriever (for next subtopic)
        graph.add_conditional_edges(
            "noter",
            self._should_continue_retrieval,
            {"retrieve": "retriever", "verify": "verifier"}
        )

        graph.add_edge("verifier", "synthesizer")
        graph.add_edge("synthesizer", END)

        return graph.compile(checkpointer=MemorySaver())

    async def investigate(self, event: str, category: str) -> InvestigationReport:
        """Run deep verification investigation"""
        logger.info(f"[DEEP-V2] Starting investigation: {event}")

        initial_state = {
            "event": event,
            "event_category": category,
            "subtopics": [],
            "structured_notes": [],
            "source_items": [],
            "conflicts_detected": [],
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
            "recursion_limit": 100,
        }

        final_state = await self.graph.ainvoke(initial_state, config)

        if final_state.get("report"):
            return InvestigationReport(**final_state["report"])

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

    async def _decompose_node(self, state: dict) -> dict:
        """
        DECOMPOSER: Split main query into 3-5 subtopics

        Like Perplexity, we break down the question into dimensions
        that need to be researched independently.
        """
        event = state["event"]
        category = state["event_category"]

        print(f"\n[DECOMPOSER] Breaking down: {event}")

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

        response = await self.llm_no_tools.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=f"Decompose: {event}")
        ])

        subtopics = self._parse_subtopics(response.content)
        print(f"[DECOMPOSER] Created {len(subtopics)} subtopics:")
        for i, st in enumerate(subtopics):
            print(f"  {i+1}. {st[:60]}...")

        return {
            **state,
            "subtopics": subtopics,
            "iteration": 0,
            "status": "retrieving",
        }

    async def _retrieve_node(self, state: dict) -> dict:
        """
        RETRIEVER: Search for current subtopic

        Multi-pass retrieval - one subtopic at a time
        """
        subtopics = state.get("subtopics", [])
        current_idx = state.get("iteration", 0)

        if current_idx >= len(subtopics):
            return {**state, "status": "noting"}

        current_subtopic = subtopics[current_idx]
        event = state["event"]

        print(f"\n[RETRIEVER] Searching subtopic {current_idx + 1}/{len(subtopics)}: {current_subtopic[:50]}...")

        prompt = f"""You are researching a specific aspect of a news event.

MAIN EVENT: {event}
CURRENT SUBTOPIC: {current_subtopic}

Search for information about this specific subtopic.
Use the most appropriate search tools:
- search_news_gdelt: FREE - For news articles (use FIRST)
- search_web_free: FREE - For general web search
- search_web: PAID - Only if free tools fail

Focus on finding:
1. Specific facts and numbers
2. Named sources and officials
3. Dates and timeline
4. Multiple perspectives

Search now for: {current_subtopic}"""

        messages = state.get("messages", [])
        messages.append(SystemMessage(content=prompt))

        response = await self.llm.ainvoke(messages)

        if hasattr(response, 'tool_calls') and response.tool_calls:
            tools = [t['name'] for t in response.tool_calls]
            print(f"[RETRIEVER] Calling: {', '.join(tools)}")

        return {
            **state,
            "messages": [*messages, response],
        }

    def _should_use_tools(self, state: dict) -> Literal["tools", "note"]:
        """Check if we need to execute tools"""
        messages = state.get("messages", [])
        if not messages:
            return "note"

        last_msg = messages[-1]
        if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
            return "tools"

        return "note"

    async def _note_node(self, state: dict) -> dict:
        """
        NOTER: Create structured notes for completed subtopic

        Synthesize findings into intermediate notes before verification
        """
        subtopics = state.get("subtopics", [])
        current_idx = state.get("iteration", 0)
        messages = state.get("messages", [])

        if current_idx >= len(subtopics):
            return {**state, "status": "verifying"}

        current_subtopic = subtopics[current_idx]

        # Extract tool results
        source_items = self._extract_sources(messages)

        print(f"\n[NOTER] Creating notes for subtopic {current_idx + 1}: {current_subtopic[:40]}...")
        print(f"[NOTER] Found {len(source_items)} sources")

        if not source_items:
            # No results, move to next subtopic
            note = {
                "subtopic": current_subtopic,
                "findings": ["No information found"],
                "sources": [],
                "conflicts": [],
                "confidence": 0.0,
            }
        else:
            # Synthesize findings
            sources_text = "\n".join([
                f"- [{s.get('source_name', 'unknown')}] {s.get('title', '')}: {s.get('content', '')[:200]}"
                for s in source_items[:15]
            ])

            prompt = f"""Analyze the search results for this subtopic.

SUBTOPIC: {current_subtopic}

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

            response = await self.llm_no_tools.ainvoke([
                SystemMessage(content=prompt),
                HumanMessage(content="Analyze and create notes")
            ])

            note = self._parse_note(response.content, current_subtopic, source_items)

        existing_notes = state.get("structured_notes", [])
        existing_sources = state.get("source_items", [])

        print(f"[NOTER] Findings: {len(note.get('findings', []))}, Conflicts: {len(note.get('conflicts', []))}")

        return {
            **state,
            "structured_notes": [*existing_notes, note],
            "source_items": [*existing_sources, *source_items],
            "iteration": current_idx + 1,
            "messages": [],  # Clear messages for next subtopic
            "status": "noting",
        }

    def _should_continue_retrieval(self, state: dict) -> Literal["retrieve", "verify"]:
        """Check if more subtopics need research"""
        subtopics = state.get("subtopics", [])
        current_idx = state.get("iteration", 0)

        if current_idx < len(subtopics):
            return "retrieve"
        return "verify"

    async def _verify_node(self, state: dict) -> dict:
        """
        VERIFIER: Cross-verify facts and detect conflicts

        Key Perplexity feature: explicit conflict detection and confidence scoring
        """
        notes = state.get("structured_notes", [])
        source_items = state.get("source_items", [])
        event = state["event"]

        print(f"\n[VERIFIER] Cross-verifying {len(notes)} subtopic notes...")

        # Compile all findings
        all_findings = []
        all_conflicts = []

        for note in notes:
            all_findings.extend(note.get("findings", []))
            all_conflicts.extend(note.get("conflicts", []))

        findings_text = "\n".join([f"- {f}" for f in all_findings[:30]])
        conflicts_text = "\n".join([f"- {c}" for c in all_conflicts]) if all_conflicts else "None detected"

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

        response = await self.llm_no_tools.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Perform deep verification")
        ])

        verified_facts, unverified, conflicts = self._parse_verification_v2(response.content)

        print(f"[VERIFIER] Verified: {len(verified_facts)}, Unverified: {len(unverified)}, Disputed: {len(conflicts)}")

        return {
            **state,
            "verified_facts": verified_facts,
            "unverified_claims": unverified,
            "conflicts_detected": conflicts,
            "status": "synthesizing",
        }

    async def _synthesize_node(self, state: dict) -> dict:
        """
        SYNTHESIZER: Generate final report with citations

        Combine all verified facts, note disputes, cite sources
        """
        event = state["event"]
        category = state["event_category"]
        verified_facts = state.get("verified_facts", [])
        unverified = state.get("unverified_claims", [])
        conflicts = state.get("conflicts_detected", [])
        source_items = state.get("source_items", [])
        notes = state.get("structured_notes", [])

        print(f"\n[SYNTHESIZER] Generating final report...")

        # Build context
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

        response = await self.llm_no_tools.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Generate final report with citations")
        ])

        # Extract unique source URLs
        sources = list(set([
            s.get("url") or s.get("source_name", "unknown")
            for s in source_items
            if s.get("url") or s.get("source_name")
        ]))

        report = {
            "event_summary": self._extract_summary(response.content),
            "category": category,
            "location": self._extract_location(event),
            "timeline": self._extract_timeline(response.content),
            "verified_facts": verified_facts,
            "media": [],
            "sources": sources[:50],  # Limit to 50
            "unverified_claims": unverified,
            "disputed_claims": conflicts,
            "confidence_score": self._calculate_overall_confidence(verified_facts),
            "generated_at": datetime.utcnow().isoformat(),
        }

        print(f"[SYNTHESIZER] Report complete: {len(verified_facts)} verified facts, {len(sources)} sources")

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
        subtopics = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("SUBTOPIC:"):
                subtopics.append(line[9:].strip())
            elif line.startswith("-") or line.startswith("•"):
                subtopics.append(line.lstrip("-• ").strip())

        # Ensure we have at least 3 subtopics
        if len(subtopics) < 3:
            subtopics = [
                "What happened? (timeline and facts)",
                "Who is involved? (actors and casualties)",
                "What is the response? (government and international)",
            ]

        return subtopics[:5]  # Max 5

    def _extract_sources(self, messages: list) -> list[dict]:
        """Extract source items from tool messages"""
        from langchain_core.messages import ToolMessage

        results = []
        for msg in messages:
            if isinstance(msg, ToolMessage):
                content = msg.content

                if isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and not item.get("error"):
                            item["source_name"] = item.get("source_name", msg.name or "unknown")
                            results.append(item)
                elif isinstance(content, dict) and not content.get("error"):
                    content["source_name"] = content.get("source_name", msg.name or "unknown")
                    results.append(content)
                elif isinstance(content, str):
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and not item.get("error"):
                                    item["source_name"] = item.get("source_name", msg.name or "unknown")
                                    results.append(item)
                    except:
                        pass

        return results

    def _parse_note(self, content: str, subtopic: str, sources: list) -> dict:
        """Parse noter output into structured note"""
        findings = []
        conflicts = []
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

        return {
            "subtopic": subtopic,
            "findings": findings,
            "sources": [s.get("source_name", "unknown") for s in sources[:10]],
            "conflicts": conflicts,
            "confidence": confidence,
        }

    def _parse_verification_v2(self, content: str) -> tuple[list, list, list]:
        """Parse verification output"""
        verified = []
        unverified = []
        disputed = []

        current = None
        current_type = None

        for line in content.split("\n"):
            line = line.strip()

            if line.startswith("VERIFIED:"):
                if current and current_type == "verified":
                    verified.append(current)
                current = {"claim": line[9:].strip()}
                current_type = "verified"
            elif line.startswith("SOURCES:") and current:
                current["supporting_sources"] = [s.strip() for s in line[8:].split(",")]
            elif line.startswith("CONFIDENCE:") and current:
                try:
                    current["confidence"] = float(line[11:].strip())
                except:
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

    def _calculate_overall_confidence(self, verified_facts: list) -> float:
        """Calculate overall report confidence"""
        if not verified_facts:
            return 0.0

        scores = [f.get("confidence", 0.5) for f in verified_facts if isinstance(f, dict)]
        return sum(scores) / len(scores) if scores else 0.5

    def _extract_summary(self, content: str) -> str:
        """Extract summary from report"""
        lines = content.split("\n")
        in_summary = False
        summary_lines = []

        for line in lines:
            if "SUMMARY" in line.upper():
                in_summary = True
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    summary_lines.append(parts[1].strip())
                continue

            if in_summary:
                if any(s in line.upper() for s in ["TIMELINE:", "KEY FACTS:", "DISPUTED:", "UNVERIFIED:"]):
                    break
                if line.strip():
                    summary_lines.append(line.strip())

        if summary_lines:
            return " ".join(summary_lines)[:600]

        return content.split("\n\n")[0][:600] if content else ""

    def _extract_location(self, event: str) -> str | None:
        """Extract location from event"""
        import re
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
        timeline = []
        in_timeline = False

        for line in content.split("\n"):
            if "TIMELINE:" in line.upper():
                in_timeline = True
                continue
            if in_timeline:
                if line.strip().startswith(("-", "•", "*")) or (line.strip() and line.strip()[0].isdigit()):
                    timeline.append(line.strip().lstrip("-•* 0123456789.").strip())
                elif any(s in line.upper() for s in ["KEY FACTS:", "DISPUTED:", "UNVERIFIED:", "SUMMARY:"]):
                    in_timeline = False

        return timeline


# =============================================================================
# Alias for compatibility
# =============================================================================

InvestigationAgentV2 = DeepVerificationAgent
