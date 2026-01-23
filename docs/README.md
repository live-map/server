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

## Documentation Structure

```
docs/
├── README.md                    # This file (entry point)
├── OVERVIEW.md                  # System overview (all audiences)
│
├── getting-started/             # New developer onboarding
│   ├── README.md               # 5-minute quickstart
│   ├── INSTALLATION.md         # Detailed setup
│   └── PROJECT_STRUCTURE.md    # Codebase guide
│
├── concepts/                    # Core concepts (all audiences)
│   ├── TWO_SOURCE_RULE.md      # Verification standard
│   ├── SOURCE_TIERS.md         # Source credibility
│   ├── CONFIDENCE_SCORING.md   # Trust calculation
│   └── INTERNATIONAL_AFFAIRS.md # Category focus
│
├── architecture/                # Technical deep-dive
│   ├── SCANNER_PIPELINE.md     # 7-stage pipeline
│   ├── EVENT_VERIFICATION.md   # Gate 0 hybrid
│   ├── ZERO_SHOT_CLASSIFIER.md # ML classification
│   └── CLAIM_VERIFICATION.md   # v3.0 system
│
├── api/                         # API documentation
│   └── README.md               # Endpoints reference
│
├── guides/                      # How-to guides
│   ├── CONFIGURATION.md        # Settings reference
│   ├── TRIGGER_GUIDE.md        # Adding sources
│   ├── TESTING_GUIDE.md        # Testing guide
│   ├── DEPLOYMENT.md           # Production deploy
│   └── TROUBLESHOOTING.md      # Issue resolution
│
├── reference/                   # Technical reference
│   ├── DATABASE_SCHEMA.md      # DB models
│   └── GLOSSARY.md             # Terms & definitions
│
├── business/                    # Business documentation
│   ├── INVESTOR_SUMMARY.md     # Executive pitch
│   └── ROADMAP.md              # Future plans
│
├── adr/                         # Architecture decisions
│   ├── ADR-001 to ADR-006
│   └── README.md               # ADR index
│
├── algorithms/                  # Algorithm documentation
│   ├── CROSS_SOURCE_MATCHER.md
│   ├── CONFIDENCE_SCORING.md
│   └── DEDUPLICATION.md
│
├── security/                    # Security documentation
│   ├── API_KEYS.md             # Key management
│   └── DATA_HANDLING.md        # Data processing
│
└── history/                     # Project evolution
    ├── README.md               # Timeline
    ├── CHANGELOG.md            # Version history
    └── archive/                # Deprecated docs
```

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

## Contributing to Documentation

When adding new documentation:

1. Place in appropriate directory
2. Update this README index
3. Link from related documents
4. Follow markdown conventions
5. Include code examples where relevant

---

*Last updated: January 2026*
