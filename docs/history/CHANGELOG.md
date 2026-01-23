# Changelog

All notable changes to the LiveMap backend are documented here.

---

## [3.3.0] - 2026-01-23

### Added
- **Zero-shot classifier** (BART-MNLI) for event verification Stage 2
- 3-stage hybrid verification pipeline (Rules → Zero-shot → LLM)
- International affairs focus with 7 categories
- Multilingual sports pattern detection (Korean, Arabic, Chinese)

### Changed
- Event verification cost reduced from $4.80/day to $1.44/day (91% total reduction)
- Scanner now filters non-international events early

### Performance
- LLM calls reduced by 90% through zero-shot pre-filtering

---

## [3.2.0] - 2026-01-21

### Added
- Gate 0: Rule-based event verification
- Gate 1: Check-worthiness filter
- Gate 2: Specificity filter
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
