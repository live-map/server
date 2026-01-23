# Glossary

Terms and definitions used in LiveMap documentation.

---

## A

### ACLED
**Armed Conflict Location & Event Data Project**. A Tier-2 research source providing conflict data with academic methodology.

### Atomic Claim
A single, verifiable statement extracted from a larger text. Cannot be broken down further. Example: "3 soldiers were injured" is atomic; "Iran attacked and soldiers were injured" is not.

### AP Style
**Associated Press Stylebook** guidelines for news writing. LiveMap generates articles following AP Style 2024-2026 conventions.

---

## B

### BART-MNLI
**facebook/bart-large-mnli**. A zero-shot classification model used in Stage 2 of event verification. Runs locally with no API cost.

### BGE-M3
**BAAI/bge-m3**. A multilingual embedding model used for semantic clustering and similarity matching.

---

## C

### Claim Verification
The process of extracting individual claims from an event and verifying each against evidence. Uses VeriScore-style extraction and QA-based verification.

### Clustering
Grouping similar events together using embedding similarity. Reduces duplicates and identifies related reports.

### Confidence Score
A numeric value (0.00-1.00) indicating the trustworthiness of an article. Based on source count, tier credibility, and diversity.

### Cross-Source Matching
Finding the same event reported by different, independent sources. Key to the Two-Source Rule.

---

## D

### Deduplication
Removing duplicate events from the pipeline. Two-layer approach: intra-scan (within same scan) and inter-scan (against database).

### Diversity Bonus
A +0.03 confidence boost when sources come from different tiers, indicating independent verification paths.

---

## E

### Event Verification
**Gate 0** in the pipeline. Filters non-events (movies, games, history) using a 3-stage hybrid approach: rules, zero-shot ML, and LLM.

---

## F

### False Positive
An event incorrectly identified as news. Example: "New war movie releases" matched by "war" keyword.

---

## G

### Gate
A filtering stage in the pipeline that removes low-quality content:
- **Gate 0**: Event verification (real event?)
- **Gate 1**: Check-worthiness (newsworthy?)
- **Gate 2**: Specificity (specific details?)
- **Gate 3**: Evidence sufficiency (enough proof?)

### GDELT
**Global Database of Events, Language, and Tone**. A Tier-1 news source providing global news coverage including articles from Reuters, AP, BBC.

---

## H

### Hybrid Verification
Combining multiple verification methods (rules + ML + LLM) for cost-effective filtering. 91% cost reduction vs LLM-only.

---

## I

### IFCN
**International Fact-Checking Network**. Organization defining 5 principles for fact-checking that LiveMap follows.

### Investigation
The process of deeply verifying an event, extracting claims, gathering evidence, and generating an article.

---

## L

### Lifespan
FastAPI application lifecycle management. Used for loading ML models at startup and cleanup at shutdown.

### LLM
**Large Language Model**. OpenAI GPT-4o-mini used for claim verification and article generation.

---

## M

### Multi-Source
Using multiple independent sources to verify information. Core principle of LiveMap's methodology.

---

## N

### NEI
**Not Enough Information**. A verdict when evidence is insufficient to support or refute a claim.

### NOAA
**National Oceanic and Atmospheric Administration**. A Tier-1 Government source for weather alerts.

---

## P

### Pipeline
The 7-stage processing flow from event collection to article publication.

### pgvector
PostgreSQL extension for vector similarity search. Used for embedding storage and similarity queries.

---

## Q

### QA Verification
Question-Answering based verification. Generates questions from claims and answers them using evidence documents.

---

## S

### Scanner
The main component that collects events from all sources, clusters them, applies filters, and outputs verified events for investigation.

### Source Tier
Classification of data sources by credibility:
- Tier-1: Government (0.99) and Major News (0.90)
- Tier-2: Research (0.85) and Secondary News (0.75)
- Tier-3: Social (0.40), Messaging (0.35), Trends (0.30)

---

## T

### Trigger
A data source that generates events. Examples: GDELT trigger, USGS trigger, Reddit trigger.

### Two-Source Rule
Journalism standard requiring 2+ independent sources before publication. Exception: Tier-1 Government sources.

---

## U

### USGS
**United States Geological Survey**. A Tier-1 Government source for earthquake data.

---

## V

### Verdict
The conclusion of claim verification:
- **SUPPORTED**: Evidence confirms the claim
- **REFUTED**: Evidence contradicts the claim
- **NEI**: Not enough information

### VeriScore
A claim extraction methodology that breaks text into atomic, verifiable claims. LiveMap implements VeriScore-style extraction.

---

## Z

### Zero-Shot Classification
ML classification without task-specific training. BART-MNLI classifies events into categories like "military conflict" or "sports" using natural language labels.

---

## Acronyms

| Acronym | Full Form |
|---------|-----------|
| ADR | Architecture Decision Record |
| API | Application Programming Interface |
| CAMEO | Conflict and Mediation Event Observations |
| CLI | Command Line Interface |
| DB | Database |
| GDELT | Global Database of Events, Language, and Tone |
| IFCN | International Fact-Checking Network |
| LLM | Large Language Model |
| ML | Machine Learning |
| MNLI | Multi-Genre Natural Language Inference |
| NEI | Not Enough Information |
| NOAA | National Oceanic and Atmospheric Administration |
| ORM | Object-Relational Mapping |
| OSINT | Open Source Intelligence |
| SOTA | State of the Art |
| USGS | United States Geological Survey |

---

## Related Documentation

- [Overview](../OVERVIEW.md) - System overview
- [Concepts](../concepts/README.md) - Core concepts
