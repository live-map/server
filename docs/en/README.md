# LiveMap Documentation

> AI-powered international affairs news verification platform

---

## Choose Your Path

### For Investors & Business

> *"What is LiveMap and why does it matter?"*

| Document | Description |
|----------|-------------|
| [**Overview**](OVERVIEW.md) | System overview and key differentiators |
| [**Investor Summary**](business/INVESTOR_SUMMARY.md) | Executive pitch and business model |
| [**Roadmap**](business/ROADMAP.md) | Future development plans |

**Key highlights:**
- $0 source cost vs $20,000+/month competitors
- 15-60 minutes faster than traditional media
- 91% LLM cost reduction through hybrid verification

---

### For Users & Journalists

> *"How can I trust LiveMap's information?"*

| Document | Description |
|----------|-------------|
| [**Overview**](OVERVIEW.md) | How LiveMap works |
| [**Confidence Scoring**](concepts/CONFIDENCE_SCORING.md) | How trust scores are calculated |
| [**Source Tiers**](concepts/SOURCE_TIERS.md) | How sources are evaluated |
| [**Two-Source Rule**](concepts/TWO_SOURCE_RULE.md) | Why we require 2+ sources |
| [**International Affairs Focus**](concepts/INTERNATIONAL_AFFAIRS.md) | What categories we cover |

**Key principles:**
- IFCN-compliant methodology
- Transparent confidence scores
- All sources cited

---

### For Technical Experts

> *"How does the technology actually work?"*

| Document | Description |
|----------|-------------|
| [**Architecture Overview**](architecture/README.md) | System architecture |
| [**Scanner Pipeline**](architecture/SCANNER_PIPELINE.md) | 7-stage processing pipeline |
| [**Event Verification**](architecture/EVENT_VERIFICATION.md) | Gate 0 hybrid verification |
| [**Zero-shot Classifier**](architecture/ZERO_SHOT_CLASSIFIER.md) | ML-based classification |
| [**Claim Verification**](architecture/CLAIM_VERIFICATION.md) | v3.0 SOTA implementation |
| [**Algorithms**](algorithms/README.md) | Detailed algorithm documentation |
| [**ADRs**](adr/README.md) | Architecture Decision Records |

**Technical highlights:**
- 2026 SOTA implementation (AIC CTU, HerO 2, VeriScore)
- 3-stage hybrid verification (Rules → Zero-shot → LLM)
- BGE-M3 embeddings + HDBSCAN clustering

---

### For Developers

> *"How do I set up and contribute?"*

| Document | Description |
|----------|-------------|
| [**Getting Started**](getting-started/README.md) | 5-minute quickstart |
| [**Installation**](getting-started/INSTALLATION.md) | Detailed setup guide |
| [**Project Structure**](getting-started/PROJECT_STRUCTURE.md) | Codebase organization |
| [**API Reference**](api/README.md) | REST API documentation |
| [**Configuration**](guides/CONFIGURATION.md) | All settings |
| [**Trigger Guide**](guides/TRIGGER_GUIDE.md) | Adding new data sources |
| [**Testing Guide**](guides/TESTING_GUIDE.md) | Writing tests |
| [**Deployment**](guides/DEPLOYMENT.md) | Production deployment |
| [**Troubleshooting**](guides/TROUBLESHOOTING.md) | Common issues |

**Developer resources:**
- Database Schema: [reference/DATABASE_SCHEMA.md](reference/DATABASE_SCHEMA.md)
- Glossary: [reference/GLOSSARY.md](reference/GLOSSARY.md)
- Security: [security/README.md](security/README.md)

---

## Reading Guides

| Role | Guide |
|------|-------|
| Project Managers | [**READING_GUIDE.md**](READING_GUIDE.md) - 90-minute structured reading path |
| Investors | OVERVIEW → business/INVESTOR_SUMMARY → business/COMPETITIVE_ANALYSIS |
| Developers | getting-started/README → architecture → guides |

---

## Quick Links

| Need | Go To |
|------|-------|
| System overview | [OVERVIEW.md](OVERVIEW.md) |
| Setup in 5 minutes | [getting-started/README.md](getting-started/README.md) |
| API endpoints | [api/README.md](api/README.md) |
| All settings | [guides/CONFIGURATION.md](guides/CONFIGURATION.md) |
| Help with issues | [guides/TROUBLESHOOTING.md](guides/TROUBLESHOOTING.md) |

---

## Other Languages

- [**한국어 문서 (Korean)**](../ko/README.md)

---

*Last updated: January 2026*
