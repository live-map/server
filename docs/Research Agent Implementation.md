# Research Agent Implementation via LangGraph

This document explains how the LangGraph-based Research Agent automatically conducts fact-based research on poll topics, covering the pipeline architecture, how each node works, and how files orchestrate each other end-to-end.

## Table of Contents

1. [Overview](#overview)
2. [Project File Structure](#project-file-structure)
3. [How the Research Agent Initializes](#how-the-research-agent-initializes)
4. [State Management](#state-management)
5. [The 9-Node Pipeline](#the-9-node-pipeline)
6. [Node Details](#node-details)
7. [External Tools (API Clients)](#external-tools-api-clients)
8. [Prompt System](#prompt-system)
9. [Service Layer (Orchestrator)](#service-layer-orchestrator)
10. [Controller Integration (API Endpoints)](#controller-integration-api-endpoints)
11. [Complete Flow Diagrams](#complete-flow-diagrams)
12. [Key Concepts Summary](#key-concepts-summary)
13. [Environment Variables Required](#environment-variables-required)

---

## Overview

The Research Agent is a **LangGraph StateGraph pipeline** that automatically generates fact-based Korean articles for polls. When an admin triggers research on a poll, the agent:

- **Discovers diverse perspectives** on the poll topic (Stanford STORM pattern)
- **Searches the web, academic papers, and fact-check databases** in parallel
- **Analyzes coverage gaps** and runs follow-up searches (Corrective RAG pattern)
- **Generates a structured outline** avoiding naive perspective-as-section mapping
- **Synthesizes an 800-1500 character article** with numbered citations, tables, and blockquotes
- **Reviews quality** via programmatic checks + LLM scoring, retrying up to 2 times

The result is saved to `Poll.ai_content` and `PollSource` records in the database.

---

## Project File Structure

```
server/
├── app/
│   ├── core/
│   │   └── lifespan.py                  # App startup: initializes ResearchService
│   │
│   ├── api/v1/poll/
│   │   └── controller.py                # API endpoints: POST /research, GET /research/status
│   │
│   ├── models/
│   │   └── poll.py                      # Poll model (ai_content, ai_metrics columns)
│   │
│   └── services/research/               # ← The Research Agent lives here
│       ├── __init__.py                  # Exports ResearchService
│       ├── config.py                    # AISettings: API keys, model selection
│       ├── state.py                     # ResearchState TypedDict (data flowing through pipeline)
│       ├── schemas.py                   # Pydantic models for LLM structured output
│       ├── graph.py                     # LangGraph StateGraph assembly (wires 9 nodes)
│       ├── service.py                   # ResearchService: orchestrator, DB integration
│       │
│       ├── nodes/                       # 9 processing nodes
│       │   ├── perspective_discovery.py # Node 1: Identify stakeholders
│       │   ├── planner.py              # Node 2: Generate search queries
│       │   ├── web_search.py           # Node 3: Tavily web search (parallel)
│       │   ├── academic_search.py      # Node 4: Semantic Scholar papers (parallel)
│       │   ├── fact_check.py           # Node 5: Google Fact Check API (parallel)
│       │   ├── gap_analyzer.py         # Node 6: Coverage analysis + follow-up
│       │   ├── outline_generator.py    # Node 7: Article structure design
│       │   ├── synthesizer.py          # Node 8: Article generation
│       │   └── reviewer.py            # Node 9: Quality validation + retry logic
│       │
│       ├── tools/                       # External API clients
│       │   ├── tavily_client.py        # Web search with Korean domain steering
│       │   ├── jina_reader.py          # URL → markdown content extraction
│       │   ├── semantic_scholar.py     # Academic paper search
│       │   └── fact_check_client.py    # Google Fact Check verification
│       │
│       └── prompts/                     # LLM system & user prompts
│           ├── perspective_prompt.py
│           ├── planner_prompt.py
│           ├── outline_prompt.py
│           ├── synthesizer_prompt.py
│           └── reviewer_prompt.py
```

---

## How the Research Agent Initializes

The agent is initialized at FastAPI startup via the lifespan context manager, then exposed through API endpoints.

### Initialization Chain

```
FastAPI app starts
        ↓
app/core/lifespan.py  →  lifespan()
        ↓
Loads AISettings from .env  (config.py)
        ↓
Checks ai_settings.research_enabled
(requires at least one LLM key + TAVILY_API_KEY)
        ↓
Creates ResearchService()  (service.py)
        ↓
ResearchService.__init__() calls build_research_graph()  (graph.py)
        ↓
graph.py wires 9 nodes into a LangGraph StateGraph
        ↓
Stores service on app.state.research_service
        ↓
Poll controller reads app.state.research_service
to handle /research endpoints
```

**`app/core/lifespan.py`** — App startup hook:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ...
    try:
        from app.services.research.config import ai_settings

        if ai_settings.research_enabled:
            from app.services.research.service import ResearchService
            app.state.research_service = ResearchService()
        else:
            app.state.research_service = None
    except Exception as e:
        app.state.research_service = None

    yield  # App runs here

    # Shutdown
```

**`app/services/research/config.py`** — `AISettings` class:

```python
class AISettings:
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    TAVILY_API_KEY: str = ""

    # Role-based model selection
    AI_MODEL: str = "claude-sonnet-4-5-20250929"     # Default
    AI_MODEL_PLANNER: str = "gpt-4o-mini"            # Cheap, fast
    AI_MODEL_SYNTHESIZER: str = "gpt-4o"             # High quality
    AI_MODEL_REVIEWER: str = "gpt-4o"                # Strict validation

    @property
    def research_enabled(self) -> bool:
        # True if at least one LLM key + Tavily key configured
        ...

    def get_chat_model(self, role, max_tokens, temperature):
        # Returns ChatAnthropic or ChatOpenAI based on provider
        ...
```

---

## State Management

### `ResearchState` (state.py)

A single `TypedDict` flows through all 9 nodes, accumulating data at each step:

```python
class ResearchState(TypedDict):
    # ─── Input (from poll) ───
    poll_id: str
    poll_title: str
    poll_description: str
    poll_options: list[str]           # e.g., ["찬성", "반대"]
    poll_category: str

    # ─── Node 1 output ───
    perspectives: list[Perspective]   # e.g., [{"label": "노동계", ...}]

    # ─── Node 2 output ───
    search_queries: list[str]         # 6-8 Korean web queries
    academic_queries: list[str]       # 2-4 English academic queries
    fact_check_claims: list[str]      # 2-4 claims to verify

    # ─── Nodes 3-5 output (append-only via operator.add) ───
    web_sources: Annotated[list[SourceItem], operator.add]
    academic_sources: Annotated[list[SourceItem], operator.add]
    fact_check_results: Annotated[list[dict], operator.add]

    # ─── Node 6 output ───
    gap_report: dict                  # Coverage analysis

    # ─── Node 7 output ───
    outline: list[OutlineSection]     # Article structure

    # ─── Nodes 8-9 output ───
    draft_article: str
    review_feedback: str
    final_article: str
    extracted_sources: list[SourceItem]

    # ─── Control flow ───
    retry_count: int
    error: str
```

### `SourceItem` (state.py)

Each source collected from web, academic, or fact-check search:

```python
class SourceItem(TypedDict):
    title: str
    url: str
    source_type: str        # NEWS | PAPER | ARTICLE | OTHER
    description: str        # Author/publisher for papers
    content_snippet: str    # Raw content (800-2000 chars)
    credibility: str        # HIGH | MEDIUM | LOW
```

### `Pydantic Schemas` (schemas.py)

Used with LangChain's `with_structured_output()` to ensure the LLM returns validated JSON:

| Schema              | Used By          | Fields                                         |
| ------------------- | ---------------- | ---------------------------------------------- |
| `PerspectiveOutput` | Node 1           | 2-6 perspectives with labels + key questions   |
| `PlannerOutput`     | Node 2           | search_queries, academic_queries, fact_check_claims |
| `GapReport`         | Node 6           | covered/gap perspectives + follow-up queries   |
| `OutlineOutput`     | Node 7           | 2-6 sections with key points + source refs     |
| `ReviewerOutput`    | Node 9           | pass/fail verdict + score (0-100) + feedback   |

---

## The 9-Node Pipeline

### Graph Assembly (graph.py)

`graph.py` wires the 9 nodes into a LangGraph `StateGraph`:

```python
def build_research_graph() -> CompiledGraph:
    graph = StateGraph(ResearchState)

    # Add nodes
    graph.add_node("perspective_discovery", perspective_discovery_node)
    graph.add_node("planner", planner_node)
    graph.add_node("web_search", web_search_node)
    graph.add_node("academic_search", academic_search_node)
    graph.add_node("fact_check", fact_check_node)
    graph.add_node("gap_analyzer", gap_analyzer_node)
    graph.add_node("outline_generator", outline_generator_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("reviewer", reviewer_node)

    # Wire edges
    graph.set_entry_point("perspective_discovery")
    graph.add_edge("perspective_discovery", "planner")

    # Parallel fan-out: planner → [web, academic, fact_check]
    graph.add_edge("planner", "web_search")
    graph.add_edge("planner", "academic_search")
    graph.add_edge("planner", "fact_check")

    # Fan-in: [web, academic, fact_check] → gap_analyzer
    graph.add_edge("web_search", "gap_analyzer")
    graph.add_edge("academic_search", "gap_analyzer")
    graph.add_edge("fact_check", "gap_analyzer")

    # Sequential
    graph.add_edge("gap_analyzer", "outline_generator")
    graph.add_edge("outline_generator", "synthesizer")
    graph.add_edge("synthesizer", "reviewer")

    # Conditional: reviewer → END or → synthesizer (retry)
    graph.add_conditional_edges("reviewer", _review_decision, {
        "end": END,
        "revise": "synthesizer",
    })

    return graph.compile()
```

### Pipeline Diagram

```
START
  ↓
┌─────────────────────────────────────────────────┐
│  Node 1: perspective_discovery                  │
│  "Who are the stakeholders on this topic?"      │
│                                                 │
│  Input:  poll_title, poll_description, options  │
│  Output: perspectives[]                         │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Node 2: planner                                │
│  "Generate targeted search queries"             │
│                                                 │
│  Input:  poll info + perspectives               │
│  Output: search_queries[], academic_queries[],  │
│          fact_check_claims[]                     │
└────────────────────┬────────────────────────────┘
                     ↓
          ┌──────────┼──────────┐
          ↓          ↓          ↓
     ┌─────────┐ ┌────────┐ ┌─────────┐
     │ Node 3  │ │ Node 4 │ │ Node 5  │
     │ web_    │ │ academ │ │ fact_   │
     │ search  │ │ _search│ │ check   │
     │ (Tavily)│ │ (S2)   │ │ (Google)│
     └────┬────┘ └───┬────┘ └────┬────┘
          │          │           │
          └──────────┼───────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Node 6: gap_analyzer  (CRAG pattern)           │
│  "Are all perspectives covered by sources?"     │
│                                                 │
│  Input:  perspectives + all sources             │
│  Output: gap_report + optional follow-up sources│
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Node 7: outline_generator  (STORM style)       │
│  "Design article structure from sources"        │
│                                                 │
│  Input:  sources + perspectives + gap_report    │
│  Output: outline[] (3-5 sections)               │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Node 8: synthesizer                            │
│  "Write 800-1500 char article with citations"   │
│                                                 │
│  Input:  outline + numbered sources             │
│  Output: draft_article, extracted_sources       │
└────────────────────┬────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────┐
│  Node 9: reviewer                               │
│  "Validate quality: programmatic + LLM check"   │
│                                                 │
│  Input:  draft_article + sources                │
│  Output: final_article OR review_feedback       │
└────────────────────┬────────────────────────────┘
                     ↓
              ┌──────┴──────┐
              ↓             ↓
            PASS          FAIL
              ↓        (retry ≤ 2)
         final_article     ↓
              ↓        synthesizer
             END       (with feedback)
```

### Conditional Routing (graph.py)

```python
def _review_decision(state: ResearchState) -> str:
    if state.get("final_article"):
        return "end"          # Reviewer passed → done
    if state.get("retry_count", 0) >= 2:
        return "end"          # Max retries reached → use draft as-is
    return "revise"           # Reviewer failed → loop back to synthesizer
```

---

## Node Details

### Node 1: Perspective Discovery

**File**: `nodes/perspective_discovery.py`
**Prompt**: `prompts/perspective_prompt.py`

**Purpose**: Identify 3-5 stakeholders and viewpoints on the poll topic, following the Stanford STORM research pattern.

**How it works**:

1. Receives poll title, description, category, and options from state
2. Calls LLM with `PerspectiveOutput` structured output schema
3. LLM returns a list of perspectives with labels and key questions

**Input → Output**:

```
Input:  poll_title="주 4일제 도입, 찬성하십니까?"
        poll_options=["찬성", "반대"]

Output: perspectives=[
            {"label": "노동계", "description": "근무 시간 단축...",
             "key_questions": ["생산성 변화는?", "해외 사례는?"]},
            {"label": "경영계", "description": "인건비 부담...",
             "key_questions": ["기업 비용은?", "생산성 감소?"]},
            {"label": "정책 전문가", "description": "제도적 설계...",
             "key_questions": ["법적 근거?", "단계적 도입?"]}
        ]
```

**Fallback**: If LLM fails, uses poll options as perspectives directly.

**Orchestration**:
- `perspective_discovery.py` imports prompt from `prompts/perspective_prompt.py`
- `perspective_discovery.py` imports `PerspectiveOutput` schema from `schemas.py`
- `perspective_discovery.py` imports `get_chat_model()` from `config.py`
- Result flows into state → consumed by `planner.py` (Node 2)

---

### Node 2: Planner

**File**: `nodes/planner.py`
**Prompt**: `prompts/planner_prompt.py`

**Purpose**: Generate targeted, data-centric search queries based on the discovered perspectives.

**How it works**:

1. Formats perspectives with their key questions
2. Calls LLM with `PlannerOutput` structured output schema
3. Enforces Korean web queries with data-centric patterns, English academic queries, and fact-check claims

**Query Generation Rules**:

```
Good patterns:  "주 4일제 시행 기업 생산성 변화 통계 2024"
Bad patterns:   "필요성", "장단점", "의견", "해야 하는 이유"
```

**Output**:

```python
{
    "search_queries": [        # 6-8 Korean web queries
        "주 4일제 시행 기업 생산성 변화 통계 2024",
        "OECD 주 4일 근무 국가 경제 성과 비교",
        ...
    ],
    "academic_queries": [      # 2-4 English academic queries
        "four-day work week productivity",
        "reduced working hours economic impact"
    ],
    "fact_check_claims": [     # 2-4 claims to verify
        "주 4일제 도입 시 생산성이 20% 증가한다",
        ...
    ]
}
```

**Fallback**: If structured output fails, generates queries from perspective labels + key questions.

**Orchestration**:
- `planner.py` reads `perspectives` from state (produced by Node 1)
- `planner.py` imports prompt from `prompts/planner_prompt.py`
- Output queries are consumed in parallel by Nodes 3, 4, and 5

---

### Node 3: Web Search

**File**: `nodes/web_search.py`
**Tool**: `tools/tavily_client.py` + `tools/jina_reader.py`

**Purpose**: Collect web articles, news, and reports via Tavily search, with Korean domain steering.

**How it works**:

1. Takes `search_queries` from state
2. Executes all queries in parallel via `asyncio.gather()`
3. For each query:
   - Calls `TavilyClient.search()` with `search_depth="advanced"`
   - Filters results against a blocklist (namu.wiki, blog.naver.com, wikipedia, youtube, etc.)
   - If a snippet is too short (<200 chars), enriches it via `JinaReader` (URL → markdown)
4. Deduplicates by URL
5. Boosts trusted Korean domains (korea.kr, yonhapnews.co.kr, etc.) to `credibility=HIGH`
6. Sorts by credibility

**Domain Controls**:

| Category        | Domains                                                    |
| --------------- | ---------------------------------------------------------- |
| **Blocked**     | namu.wiki, blog.naver.com, wikipedia.org, youtube.com, tistory, medium, reddit |
| **Trusted KR**  | korea.kr, yonhapnews.co.kr, hani.co.kr, chosun.com, kostat.go.kr |
| **Trusted Intl**| reuters.com, bbc.com, apnews.com                           |

**Output**: `web_sources: list[SourceItem]` (max ~20 deduplicated results)

**Orchestration**:
- `web_search.py` imports `TavilyClient` from `tools/tavily_client.py`
- `web_search.py` imports `JinaReader` from `tools/jina_reader.py`
- Results are appended to state via `operator.add` (merge with other search nodes)
- All three search nodes (3, 4, 5) run in **parallel** and fan-in to Node 6

---

### Node 4: Academic Search

**File**: `nodes/academic_search.py`
**Tool**: `tools/semantic_scholar.py`

**Purpose**: Find peer-reviewed papers via Semantic Scholar's free API.

**How it works**:

1. Takes `academic_queries` from state
2. Executes queries **sequentially** (1-second delay between requests for rate limiting)
3. Each query returns max 3 results with: title, abstract, url, citationCount, year, authors
4. Assigns credibility by citation count:

| Citations | Credibility |
| --------- | ----------- |
| > 50      | HIGH        |
| > 10      | MEDIUM      |
| else      | LOW         |

**Output**: `academic_sources: list[SourceItem]` (max ~12 papers)

**Orchestration**:
- `academic_search.py` imports `SemanticScholarClient` from `tools/semantic_scholar.py`
- Runs in parallel with Nodes 3 and 5
- Results merge into state via `operator.add`

---

### Node 5: Fact Check

**File**: `nodes/fact_check.py`
**Tool**: `tools/fact_check_client.py`

**Purpose**: Verify claims against fact-checking organizations via Google Fact Check API.

**How it works**:

1. Takes `fact_check_claims` from state
2. Executes all claims in parallel via `asyncio.gather()`
3. Returns structured results: claim_text, rating, publisher, URL

**Output**: `fact_check_results: list[dict]`

**Orchestration**:
- `fact_check.py` imports `FactCheckClient` from `tools/fact_check_client.py`
- Runs in parallel with Nodes 3 and 4
- Results merge into state via `operator.add`
- If `GOOGLE_FACT_CHECK_API_KEY` is not configured, returns empty list gracefully

---

### Node 6: Gap Analyzer

**File**: `nodes/gap_analyzer.py`
**Tool**: `tools/tavily_client.py` (for follow-up searches)

**Purpose**: Validate that every perspective has adequate source coverage, using the **CRAG (Corrective RAG)** pattern.

**How it works**:

1. Receives all sources from Nodes 3-5 + perspectives from Node 1
2. LLM analyzes: "For each perspective, are there >=2 credible sources?"
3. Identifies gaps (under-covered perspectives)
4. Generates follow-up search queries for gaps
5. **If gaps found**: Runs up to 3 additional Tavily searches
6. Appends new results via `operator.add`

**Output**:

```python
{
    "gap_report": {
        "covered": ["노동계", "경영계"],
        "gaps": ["정책 전문가"],
        "summary": "정책 전문가 관점의 출처가 부족합니다"
    },
    # + additional web_sources from follow-up searches
}
```

**Orchestration**:
- `gap_analyzer.py` reads `perspectives` (Node 1) + all sources (Nodes 3-5) from state
- `gap_analyzer.py` imports `TavilyClient` from `tools/tavily_client.py` for follow-ups
- Uses `GapReport` schema from `schemas.py`
- Output feeds into Node 7 (outline_generator)

---

### Node 7: Outline Generator

**File**: `nodes/outline_generator.py`
**Prompt**: `prompts/outline_prompt.py`

**Purpose**: Design article structure following the STORM style, avoiding naive perspective-as-section mapping.

**How it works**:

1. Receives sources + perspectives + gap report
2. LLM designs 3-5 sections with key points and source references
3. **Post-processing**:
   - Removes any conclusion/summary sections (결론, 요약, 정리, 마무리)
   - Checks if >50% of sections map 1:1 to poll options → if so, **regenerates** with a warning

**Good vs Bad Outlines**:

```
Good:
  ## 딥페이크 성범죄 실태와 피해 규모
  ## 해외 규제와 국내법 비교
  ## 처벌 강화와 표현의 자유, 양립 가능한가

Bad:
  ## 찬성 입장       ← directly maps to poll option
  ## 반대 입장       ← directly maps to poll option
  ## 결론            ← conclusion section
```

**Output**:

```python
outline = [
    {
        "title": "## 현황과 국제 비교",
        "key_points": ["2024 현황 데이터", "OECD 비교"],
        "source_numbers": [1, 3, 5]
    },
    ...
]
```

**Orchestration**:
- `outline_generator.py` reads all accumulated sources + gap_report from state
- `outline_generator.py` imports prompt from `prompts/outline_prompt.py`
- Uses `OutlineOutput` schema from `schemas.py`
- Output feeds into Node 8 (synthesizer)

---

### Node 8: Synthesizer

**File**: `nodes/synthesizer.py`
**Prompt**: `prompts/synthesizer_prompt.py`

**Purpose**: Generate the final 800-1500 character article with numbered citations, tables, and blockquotes.

**How it works**:

1. Builds a pre-numbered source list: `[1] Title (HIGH) — snippet...`
2. Passes outline + sources to LLM
3. LLM generates article following the outline structure
4. **Post-processing pipeline**:
   - Strips any conclusion sections via regex
   - Auto-bolds numbers if no bold formatting exists
   - Ensures at least 2 visual elements (bold + table/blockquote)

**Anti-Hallucination Rules**:

- Only use provided source numbers `[1]`, `[2]`, etc.
- Each cited fact must exist in the source's snippet
- Never use `[^source|URL]` legacy citation format
- If a fact isn't in any snippet, state it without a citation number

**Markdown Requirements**:

| Element      | Rule                                    |
| ------------ | --------------------------------------- |
| Numbers      | All stats must be `**bold**`            |
| Tables       | At least 1 comparison table required    |
| Blockquotes  | At least 1 expert quote (`> quote`)     |
| Headers      | Only `##` (no `#` h1)                   |
| Lists        | Only `- bullet` (no `1. 2. 3.`)        |

**Revision Mode**: If called after a reviewer rejection, receives `review_feedback` and the previous `draft_article`, then uses `SYNTHESIZER_REVISE_USER` prompt to fix specific issues.

**Output**:

```python
{
    "draft_article": "## 상속세 현황과 비교\n\n...",
    "extracted_sources": list[SourceItem],
    "confidence": {
        "source_count": 15,
        "korean_ratio": 0.67,
        "has_academic": True,
        "level": "HIGH"
    }
}
```

**Orchestration**:
- `synthesizer.py` reads `outline` (Node 7) + all sources from state
- `synthesizer.py` imports prompt from `prompts/synthesizer_prompt.py`
- On first run: uses `SYNTHESIZER_USER` prompt
- On retry: uses `SYNTHESIZER_REVISE_USER` prompt (with `review_feedback` from Node 9)
- Output feeds into Node 9 (reviewer)

---

### Node 9: Reviewer

**File**: `nodes/reviewer.py`
**Prompt**: `prompts/reviewer_prompt.py`

**Purpose**: Validate article quality with a two-stage review: programmatic checks (non-bypassable) + LLM scoring.

**Stage 1: Programmatic Review** (cannot be bypassed by LLM):

```python
def _programmatic_review(article: str) -> tuple[bool, list[str]]:
    failures = []

    # Check 1: Conclusion section exists?
    if re.search(r"#{2,3}\s*(결론|요약|정리|마무리)", article):
        failures.append("결론/요약/정리 섹션이 존재합니다")

    # Check 2: Blocked domain cited in article?
    for domain in ["namu.wiki", "blog.naver.com", ...]:
        if domain in article:
            failures.append(f"차단 도메인 '{domain}'이 포함됨")

    # Check 3: Visual elements (need 2+ of: bold, table, blockquote)
    visual_count = sum([
        "**" in article,
        "|" in article and "---" in article,
        "\n> " in article
    ])
    if visual_count < 2:
        failures.append("시각 요소 2개+ 필수 (bold, table, blockquote)")

    # Check 4: Legacy citation format?
    if re.search(r"\[\^[^\]]+\|[^\]]+\]", article):
        failures.append("[^출처|URL] 형식 금지")

    return len(failures) == 0, failures
```

If programmatic check fails → feedback returned, `retry_count` incremented, loops back to synthesizer.

**Stage 2: LLM Cross-Model Review** (if programmatic passes):

Scores 0-100 based on:
- Bias detection (balanced perspectives)
- Citation accuracy (each `[N]` matches source N content)
- Source quality (>=3 HIGH credibility sources)
- Data richness (>=2 concrete numbers)
- Structure diversity (not "perspective1 → perspective2 → conclusion")
- Korean readability (professional journalism tone)

**Scoring Deductions**:

| Issue                              | Penalty |
| ---------------------------------- | ------- |
| "~고 있습니다" repeated 3+ times   | -5      |
| Same-length sections               | -5      |
| <3 HIGH credibility sources        | -10     |
| Unsourced opinions                 | -5      |
| Numbers not bolded                 | -5      |

**Pass Threshold**: score >= 60

**Output**:

```python
# On PASS:
{"final_article": "...", "review_feedback": "", "review_score": 85}

# On FAIL:
{"review_feedback": "구체적 결론 필요...", "retry_count": 1}
```

**Orchestration**:
- `reviewer.py` reads `draft_article` and `extracted_sources` from state
- `reviewer.py` imports prompt from `prompts/reviewer_prompt.py`
- Uses `ReviewerOutput` schema from `schemas.py`
- On pass → sets `final_article` → graph routes to END
- On fail → sets `review_feedback` + increments `retry_count` → graph routes back to `synthesizer`
- Max 2 retries enforced by `_review_decision()` in `graph.py`

---

## External Tools (API Clients)

### TavilyClient (`tools/tavily_client.py`)

**Purpose**: Web search optimized for AI agents.

**Features**:
- Async wrapper around `AsyncTavilyClient`
- **Korean query steering**: Korean queries get `include_domains=[trusted Korean sources]`
- **Blocklist enforcement**: 23 domains excluded at API level
- Raw content extraction: Uses `raw_content` (2000 chars) or `content` (800 chars)
- Credibility scoring based on Tavily relevance score

**Used by**: Node 3 (web_search) and Node 6 (gap_analyzer follow-up searches)

### JinaReader (`tools/jina_reader.py`)

**Purpose**: Extract clean markdown content from a URL (free, no API key needed).

**Endpoint**: `https://r.jina.ai/{url}` → returns markdown

**Used by**: Node 3 (web_search) — enriches snippets shorter than 200 chars

### SemanticScholarClient (`tools/semantic_scholar.py`)

**Purpose**: Search academic papers via Semantic Scholar's free API.

**Endpoint**: `https://api.semanticscholar.org/graph/v1/paper/search`

**Fields returned**: title, abstract, url, citationCount, year, authors

**Used by**: Node 4 (academic_search)

### FactCheckClient (`tools/fact_check_client.py`)

**Purpose**: Verify claims against fact-checking organizations.

**Endpoint**: `https://factchecktools.googleapis.com/v1alpha1/claims:search`

**Requires**: `GOOGLE_FACT_CHECK_API_KEY` (optional — returns empty list if missing)

**Used by**: Node 5 (fact_check)

---

## Prompt System

Each node that uses an LLM has a corresponding prompt file:

| Prompt File                    | Used By       | Key Rules                                                      |
| ------------------------------ | ------------- | -------------------------------------------------------------- |
| `perspective_prompt.py`        | Node 1        | 3-5 perspectives, avoid false dichotomy, concrete questions    |
| `planner_prompt.py`            | Node 2        | Data-centric Korean queries, forbidden: "필요성", "장단점"      |
| `outline_prompt.py`            | Node 7        | STORM-style outline, no conclusion sections, no 1:1 mapping   |
| `synthesizer_prompt.py`        | Node 8        | 800-1500 chars, anti-hallucination, bold + table + blockquote  |
| `reviewer_prompt.py`           | Node 9        | 100-point scoring, deductions for repetition/bias/weak sources |

Each prompt file exports system and user message templates as string constants, which are imported by their corresponding node.

---

## Service Layer (Orchestrator)

### `ResearchService` (service.py)

The service class ties the LangGraph pipeline to the database:

```python
class ResearchService:
    def __init__(self):
        self.graph = build_research_graph()   # from graph.py
        self._research_status = {}            # in-memory status tracker

    def get_status(self, poll_id: str) -> dict:
        return self._research_status.get(poll_id, {"status": "pending"})

    async def run_research(self, poll_id: uuid.UUID, session: AsyncSession) -> None:
        # 1. Fetch poll from DB (with options)
        # 2. Build initial state from poll data
        # 3. Run graph: final_state = await self.graph.ainvoke(initial_state)
        # 4. Extract article + sources from final_state
        # 5. Update poll.ai_content + poll.ai_updated_at
        # 6. Clear old PollSource records, insert new ones (max 20)
        # 7. Commit DB transaction
        # 8. Update _research_status to "completed"
```

**How `service.py` orchestrates**:

```
service.py
  ├── imports build_research_graph() from graph.py
  ├── graph.py imports all 9 node functions from nodes/
  │   ├── each node imports its prompt from prompts/
  │   ├── each node imports schemas from schemas.py
  │   ├── each node imports get_chat_model() from config.py
  │   └── search nodes import clients from tools/
  ├── service.py reads Poll from DB via SQLAlchemy
  ├── service.py calls graph.ainvoke(initial_state)
  └── service.py writes results back to DB (Poll + PollSource)
```

---

## Controller Integration (API Endpoints)

### `app/api/v1/poll/controller.py`

Two endpoints expose the research agent:

#### Trigger Research

```
POST /api/v1/polls/{poll_id}/research
Headers: Authorization (admin token)
Response: 202 ACCEPTED
```

**Handler logic**:

1. Check `request.app.state.research_service` exists and is enabled
2. Verify the poll exists in DB
3. Check research is not already running for this poll
4. Create a FastAPI `BackgroundTasks` entry to run research asynchronously
5. Return `{"status": "started", "pollId": poll_id}`

**Background task**:

```python
async def _run_research():
    async with AsyncSessionLocal() as bg_session:
        await research_service.run_research(poll_id, bg_session)
```

#### Get Research Status

```
GET /api/v1/polls/{poll_id}/research/status
Headers: Authorization (admin token)
Response: 200 OK
```

**Handler logic**:

1. Get service from `request.app.state.research_service`
2. Query in-memory status
3. Return `{"status": "pending|running|completed|failed", "error": null}`

---

## Complete Flow Diagrams

### Complete Research Flow (Admin Triggers → Article Saved)

```
Step 1:  Admin sends POST /api/v1/polls/{poll_id}/research
         ↓
Step 2:  controller.py validates auth + poll existence
         ↓
Step 3:  controller.py creates BackgroundTask → _run_research()
         Returns 202 ACCEPTED immediately
         ↓
Step 4:  _run_research() opens new DB session
         ↓
Step 5:  ResearchService.run_research() fetches Poll from DB
         ↓
Step 6:  Builds initial ResearchState from poll data:
         {poll_id, poll_title, poll_description, poll_options, poll_category}
         ↓
Step 7:  graph.ainvoke(initial_state) starts the pipeline
         ↓
Step 8:  Node 1 (perspective_discovery):
         LLM identifies 3-5 stakeholder perspectives
         ↓
Step 9:  Node 2 (planner):
         LLM generates 6-8 Korean + 2-4 English queries + fact-check claims
         ↓
Step 10: Nodes 3, 4, 5 run IN PARALLEL:
         ├─ Node 3: TavilyClient searches web (Korean-steered)
         │          JinaReader enriches short snippets
         ├─ Node 4: SemanticScholarClient searches papers
         └─ Node 5: FactCheckClient verifies claims
         ↓
Step 11: Node 6 (gap_analyzer):
         LLM checks coverage per perspective
         If gaps found → runs follow-up Tavily searches
         ↓
Step 12: Node 7 (outline_generator):
         LLM designs 3-5 section structure
         Post-processing removes conclusions, checks for 1:1 mapping
         ↓
Step 13: Node 8 (synthesizer):
         LLM writes 800-1500 char article with [1], [2] citations
         Post-processing: strip conclusions, auto-bold, ensure visual elements
         ↓
Step 14: Node 9 (reviewer):
         a. Programmatic checks (conclusion, blocked domains, visual elements)
         b. LLM scoring (0-100)
         ↓
Step 15: If score >= 60:  → final_article set → END
         If score < 60 and retry_count < 2:
           → feedback sent back to synthesizer (Step 13)
         If retry_count >= 2:
           → draft_article used as final → END
         ↓
Step 16: ResearchService extracts final_article + sources from state
         ↓
Step 17: Updates Poll record:
         poll.ai_content = final_article
         poll.ai_updated_at = now()
         poll.ai_metrics = {score, source_count, ...}
         ↓
Step 18: Clears old PollSource records for this poll
         Inserts new PollSource records (max 20)
         ↓
Step 19: Commits DB transaction
         ↓
Step 20: Updates in-memory status to "completed"
         ↓
Step 21: Admin can GET /polls/{poll_id}/research/status → "completed"
         Frontend can display poll.ai_content to users
```

### File Orchestration Diagram

```
┌────────────────────────┐
│ app/core/lifespan.py   │ ── startup ──→ Creates ResearchService
└────────────┬───────────┘                          │
             │                                      │
             ↓                                      ↓
┌────────────────────────┐         ┌────────────────────────────┐
│ controller.py          │         │ service.py                 │
│ POST /polls/:id/       │ ──────→│ ResearchService            │
│      research          │         │   .run_research()          │
│ GET  /polls/:id/       │         │   .get_status()            │
│      research/status   │         └─────────────┬──────────────┘
└────────────────────────┘                       │
                                                 │ calls
                                                 ↓
                                    ┌────────────────────────────┐
                                    │ graph.py                   │
                                    │ build_research_graph()     │
                                    │                            │
                                    │ Wires 9 nodes into         │
                                    │ LangGraph StateGraph       │
                                    └─────────────┬──────────────┘
                                                  │ imports
                          ┌───────────────────────┬┴──────────────────────┐
                          ↓                       ↓                      ↓
             ┌─────────────────┐    ┌──────────────────┐   ┌─────────────────┐
             │ nodes/          │    │ prompts/          │   │ tools/          │
             │                 │    │                   │   │                 │
             │ Each node func  │←───│ Exports string    │   │ TavilyClient   │
             │ imports its     │    │ templates for     │   │ JinaReader     │
             │ prompt + schema │    │ system/user msgs  │   │ SemanticScholar│
             │ + config model  │    │                   │   │ FactCheckClient│
             └────────┬────────┘    └───────────────────┘   └───────┬────────┘
                      │                                             │
                      │                                             │
                      ↓                                             │
             ┌─────────────────┐                                    │
             │ schemas.py      │                                    │
             │ Pydantic models │   ←────── used by nodes for ──────┘
             │ for structured  │          structured LLM output
             │ LLM output      │
             └────────┬────────┘
                      │
                      ↓
             ┌─────────────────┐
             │ state.py        │
             │ ResearchState   │ ← shared TypedDict flowing through all nodes
             │ SourceItem      │
             └─────────────────┘
                      │
                      ↓
             ┌─────────────────┐
             │ config.py       │
             │ AISettings      │ ← API keys, model selection, provider detection
             │ get_chat_model()│
             └─────────────────┘
```

---

## Key Concepts Summary

| Concept                     | Purpose                                                         |
| --------------------------- | --------------------------------------------------------------- |
| **LangGraph StateGraph**    | Orchestrates 9 nodes as a directed graph with conditional edges |
| **ResearchState**           | Single TypedDict that accumulates data across all nodes         |
| **operator.add**            | Allows parallel search nodes to append results without overwrite|
| **Stanford STORM pattern**  | Perspective-first research for balanced coverage                |
| **CRAG pattern**            | Corrective RAG — detect gaps and run follow-up searches         |
| **Structured Output**       | Pydantic schemas + `with_structured_output()` for validated LLM responses |
| **Multi-Model Strategy**    | Cheap planner (gpt-4o-mini) → quality synthesizer (gpt-4o) → strict reviewer (gpt-4o) |
| **Two-Stage Review**        | Programmatic gate (non-bypassable) + LLM scoring (flexible)    |
| **Anti-Hallucination**      | Source-number-only citations, snippet-match validation          |
| **Korean Domain Steering**  | Trusted Korean domains boosted, blogs/wikis blocked             |
| **BackgroundTasks**         | FastAPI runs research asynchronously, returns 202 immediately   |
| **ResearchService**         | Orchestrator that connects LangGraph to DB (Poll + PollSource)  |

---

## Environment Variables Required

```env
# LLM Provider (at least one required)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Web Search (required)
TAVILY_API_KEY=tvly-...

# Academic Search (optional — free tier works without key)
SEMANTIC_SCHOLAR_API_KEY=...

# Fact Check (optional — returns empty if missing)
GOOGLE_FACT_CHECK_API_KEY=...

# Model Overrides (optional — defaults shown)
AI_MODEL=claude-sonnet-4-5-20250929
AI_MODEL_PLANNER=gpt-4o-mini
AI_MODEL_SYNTHESIZER=gpt-4o
AI_MODEL_REVIEWER=gpt-4o
```
