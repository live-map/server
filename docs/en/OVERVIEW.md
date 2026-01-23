# LiveMap System Overview

> AI-powered international affairs news verification platform

---

## What is LiveMap?

LiveMap is an autonomous news intelligence system that monitors global events across 14+ sources, verifies information through multi-source cross-checking, and generates bilingual (Korean/English) news articles in real-time.

**Mission**: *"Faster than anyone, verified, unbiased international affairs news"*

---

## Key Differentiators

| Feature | Traditional Media | Social Media | LiveMap |
|---------|------------------|--------------|---------|
| **Detection Speed** | 15-60 min lag | Real-time | Real-time |
| **Verification** | Manual | None | Automated multi-source |
| **Bias** | Editorial decisions | Algorithmic amplification | Algorithm-based, neutral |
| **Transparency** | Rarely disclosed | Black box | Open methodology + confidence scores |
| **Source Cost** | Expensive subscriptions | Free but unreliable | $0 (all free sources) |

---

## How It Works

### 7-Stage Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. TRIGGER COLLECTION                                           │
│    GDELT, Reddit, USGS, NOAA → 14+ sources in parallel          │
├─────────────────────────────────────────────────────────────────┤
│ 2. SEMANTIC CLUSTERING                                          │
│    Group similar events using embeddings (BGE-M3)               │
├─────────────────────────────────────────────────────────────────┤
│ 3. SOURCE CLASSIFICATION                                        │
│    Tier-1 Govt | Tier-1 News | Tier-2 | Tier-3 Social           │
├─────────────────────────────────────────────────────────────────┤
│ 4. EVENT VERIFICATION (Gate 0)                                  │
│    Rules → Zero-shot ML → LLM (3-stage hybrid, 91% cost saving) │
├─────────────────────────────────────────────────────────────────┤
│ 5. CONFIDENCE SCORING                                           │
│    Two-Source Rule, tier-weighted scoring                       │
├─────────────────────────────────────────────────────────────────┤
│ 6. CONTENT GATES (Gate 1-2)                                     │
│    Check-worthiness, Specificity filters                        │
├─────────────────────────────────────────────────────────────────┤
│ 7. CLAIM VERIFICATION & ARTICLE GENERATION                      │
│    VeriScore-style claims → QA verification → AP Style article  │
└─────────────────────────────────────────────────────────────────┘
```

### Source Tier System

| Tier | Sources | Credibility | Trust Level |
|------|---------|-------------|-------------|
| **Tier-1 Govt** | USGS, NOAA | 0.99 | Immediate publish |
| **Tier-1 News** | GDELT (Reuters, AP, BBC) | 0.90 | Publishable |
| **Tier-2 Data** | ACLED | 0.85 | Needs corroboration |
| **Tier-2 News** | Currents, WorldNews | 0.75 | Needs corroboration |
| **Tier-3 Social** | Reddit, Bluesky | 0.40 | Signal only |
| **Tier-3 Msg** | Telegram | 0.35 | Signal only |

---

## Core Principles

### Two-Source Rule

Events require verification from **2+ independent sources** before publication.

**Exceptions**:
- Tier-1 Government sources (USGS, NOAA) can publish immediately
- Tier-1 News with confidence ≥ 0.70

### IFCN Compliance

We follow all 5 principles of the International Fact-Checking Network:

1. **Non-partisanship**: Algorithm-based, no editorial bias
2. **Source Transparency**: All sources cited in every article
3. **Funding Transparency**: No advertising or sponsored content
4. **Methodology Transparency**: Open documentation
5. **Corrections Policy**: Immediate correction on errors

---

## International Affairs Focus

Currently focused on 7 categories:

| Category | Description | Examples |
|----------|-------------|----------|
| **war** | Armed conflict, invasions | Russia-Ukraine, Gaza |
| **conflict** | Regional disputes | Border clashes, civil wars |
| **politics** | Summits, sanctions, elections | US-China summit |
| **security** | Nuclear, cyber, terror threats | Iran nuclear talks |
| **military** | Operations, deployments | NATO exercises |
| **terrorism** | Terror attacks, organizations | ISIS, Al-Qaeda |
| **diplomacy** | Treaties, negotiations | Peace agreements |

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy 2.0 |
| **Database** | PostgreSQL 15+ with pgvector |
| **ML Models** | BART-MNLI (zero-shot), BGE-M3 (embeddings) |
| **LLM** | OpenAI GPT-4o-mini |
| **Agent Framework** | LangGraph |

---

## Quick Links

### For Investors
- [Investor Summary](business/INVESTOR_SUMMARY.md) - Executive pitch
- [Roadmap](business/ROADMAP.md) - Future plans

### For Users
- [Confidence Scoring](concepts/CONFIDENCE_SCORING.md) - How trust scores work
- [International Affairs Focus](concepts/INTERNATIONAL_AFFAIRS.md) - Category definitions

### For Technical Experts
- [Scanner Pipeline](architecture/SCANNER_PIPELINE.md) - Full pipeline details
- [Event Verification](architecture/EVENT_VERIFICATION.md) - Gate 0 hybrid system
- [Claim Verification](architecture/CLAIM_VERIFICATION.md) - v3.0 SOTA implementation

### For Developers
- [Getting Started](getting-started/README.md) - 5-minute setup
- [Project Structure](getting-started/PROJECT_STRUCTURE.md) - Codebase guide
- [API Reference](api/README.md) - REST endpoints

---

## Cost Structure

### Source Costs: $0/month

| Source | Cost |
|--------|------|
| GDELT | Free |
| Reddit | Free |
| USGS/NOAA | Free |
| Currents API | Free (1,000/day) |
| World News API | Free (500/day) |

### Operating Costs: ~$150-250/month

| Component | Cost |
|-----------|------|
| LLM API (GPT-4o-mini) | $40-150/month |
| Cloud hosting | $50-100/month |
| Vector database | ~$50/month |

---

## Performance Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Detection latency | < 15 min | In development |
| False positive rate | < 5% | In development |
| Source coverage | 14+ sources | Implementing |
| Verification accuracy | > 90% | In development |
| LLM cost reduction | > 80% | **91% achieved** |

---

---

## References

### Data Sources
- **GDELT Project**: [gdeltproject.org](https://www.gdeltproject.org/) - Global Event, Language, and Tone database
- **ACLED**: [acleddata.com](https://acleddata.com/) - Armed Conflict Location & Event Data Project

### ML Models
- **BART-MNLI**: [facebook/bart-large-mnli](https://huggingface.co/facebook/bart-large-mnli) - Zero-shot classification model
- **BGE-M3**: [BAAI/bge-m3](https://huggingface.co/BAAI/bge-m3) - Multilingual embedding model

### Journalism Standards
- **IFCN**: [ifcncodeofprinciples.poynter.org](https://www.ifcncodeofprinciples.poynter.org/) - International Fact-Checking Network Code of Principles

---

*For detailed technical documentation, see [Architecture](architecture/README.md)*
