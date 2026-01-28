# Changelog

All notable changes to the LiveMap backend are documented here.

---

## [3.6.1] - 2026-01-27

### Added
- **Temporal Classification Enhancement** (`llm_classifier.py`) - Phase 6.1
  - `TemporalCategory` enum (BREAKING, DEVELOPING, RETROSPECTIVE, PREDICTIVE, TIMELESS)
  - Current date context in classification prompt
  - Temporal linguistic markers for improved classification
  - Auto-reject RETROSPECTIVE and PREDICTIVE articles
- Temporal classification settings
  - `temporal_classification_enabled`
  - `temporal_filter_enabled`
  - `temporal_reject_categories`

### Changed
- Prompt length increased (~300 → ~600 tokens)
- Retrospective/analysis article filtering accuracy improved (~85% → ~95%)

### Performance
- Early filtering of non-publishable articles (retrospective/predictive) improves pipeline efficiency

---

## [3.6.0] - 2026-01-27

### Added
- **LLM Classifier** (`llm_classifier.py`) - Deepinfra Llama 3.1 8B based
  - Single prompt for is_news, category, is_significant classification
  - Replaces Gate 0-2 pattern-based filtering
  - Batch processing support (default 20 articles)
- **Domain Whitelist** (`source_tiers.py`) - Only 59 Tier-1/2 domains allowed
- **Pre-LLM Title Deduplication** - Cost savings by deduplicating before LLM calls
- `dedup_before_llm` config option

### Changed
- **Recency Filter Disabled** - Already handled at trigger level
  - `recency_filter_enabled: bool = False`
  - Triple validation → Single validation simplification
- Title Deduplication moved from Step 6.5 to Step 3.34
- Tier-3 sources (Reddit, etc.) disabled by default

### Removed
- Scanner level Recency Filter (conditionally disabled)
- Pattern-based Gate dependency (in LLM mode)

### Performance
- ~25% LLM cost reduction (Pre-LLM dedup)
- 600+ regex patterns → 1 prompt
- Estimated monthly cost: $3-5 (Deepinfra)

---

## [3.5.0] - 2026-01-24

### Added
- **P2 Pipeline Metrics System**: Per-stage tracking with pass/reject rates
- **Centralized Patterns Module**: Consolidated regex patterns for maintainability
- **Early Importance Filter**: Filter low-importance events before gate processing

### Changed
- LLM timeout reduced to 30 seconds for faster failure recovery
- Error tracking improved with structured logging

### Removed
- Dead code cleanup: ~500 lines of unused code removed

### Performance
- Pipeline visibility: Full observability across 7 filter stages

---

## [3.4.0] - 2026-01-24

### Added
- **Breaking News Fast-Path (P0)**: Tier-1/2 sources can skip verification gates
- **Domain Tier System**: 4-tier domain-based credibility (Tier-1 to Tier-4)
- **Goldstein Scale Importance Scoring (P1)**: 6-dimension event importance evaluation
- **Multi-Search Engine Support**: DuckDuckGo, Google, Bing with fallback
- **Currents API Trigger**: New Tier-2 news source
- **WorldNews API Trigger**: Multi-language news aggregation

### Changed
- Confidence scoring now integrates domain tier evaluation
- Two-Source Rule: Tier-1/2 domains can publish with single source
- Cross-source matching threshold: 0.70 → 0.75

### Performance
- Breaking news latency: 45s → 5s (-89%)
- Low-importance events filtered: +40% reduction in processing

---

## [3.3.0] - 2026-01-23

### Added
- **Zero-shot classifier** (BART-MNLI) for event verification Stage 2
- 3-stage hybrid verification pipeline (Rules → Zero-shot → LLM)
- International affairs focus with 8 categories
- Multilingual sports pattern detection (Korean, Arabic, Chinese)
- Related sources section for legal compliance
- URL date extraction for recency filtering
- Wikipedia/archive source blocking

### Changed
- Event verification cost reduced from $4.80/day to $1.44/day (91% total reduction)
- Scanner now filters non-international events early
- Categories expanded from 7 to 8 (added Nuclear/WMD)

### Performance
- LLM calls reduced by 90% through zero-shot pre-filtering

---

## [3.2.0] - 2026-01-21

### Added
- Gate 0: Rule-based event verification
- Gate 1: Check-worthiness filter
- Gate 2: Specificity filter
- Gate 3: Evidence sufficiency gate
- DBSCAN event clustering for story grouping
- Evidence grounding enforcement
- Source credibility weighting
- Two-source minimum requirement
- Scanner-Agent integration

### Changed
- Pipeline now 7 stages (added Gate system)
- Non-English articles exempt from specificity check

---

## [3.1.0] - 2026-01-14

### Added
- LLM timeout (60 seconds)
- Parallel claim verification with `asyncio.gather()`
- Input validation (min/max length)
- Error recovery in scanner loop

### Changed
- Migrated to Pydantic v2 `ConfigDict`

### Fixed
- 15 code quality issues identified in deep analysis

---

## [3.0.0] - 2026-01-14

### Added
- **Claim-level verification** (VeriScore style)
- QA-based LLM verification (AIC CTU approach)
- AP Style article generation
- 5-stage investigation pipeline:
  1. Claim extraction
  2. Evidence retrieval
  3. QA verification
  4. Aggregation
  5. Article synthesis

### Changed
- Replaced event-level verification with claim-level
- Updated to 2026 SOTA approaches

### References
- AIC CTU (FEVER 8 Winner)
- HerO 2 (AVeriTeC 2025)
- VeriScore

---

## [2.0.0] - 2026-01-13

### Added
- Deep verification agent
- LangGraph integration
- Parallel evidence gathering
- Multi-source search tools

### Changed
- Agent-based architecture replaces simple pipeline

---

## [1.0.0] - 2026-01-11

### Added
- 3-stage verification pipeline
- Source tier system (Tier 1-3)
- Two-Source Rule implementation
- Confidence scoring

---

## [0.1.0] - 2026-01-10

### Added
- Initial project setup
- Telegram MCP integration
- GDELT trigger
- Basic event detection

---

## Legend

- **Added**: New features
- **Changed**: Changes in existing functionality
- **Deprecated**: Soon-to-be removed features
- **Removed**: Removed features
- **Fixed**: Bug fixes
- **Security**: Security updates
- **Performance**: Performance improvements
