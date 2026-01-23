# Reference Documentation

Technical reference materials for developers.

---

## Contents

- **[Database Schema](DATABASE_SCHEMA.md)** - SQLAlchemy models and database structure
- **[Glossary](GLOSSARY.md)** - Terms and definitions

---

## Quick Reference

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/v1/agent/scan` | POST | Trigger scan |
| `/api/v1/agent/status` | GET | Agent status |
| `/api/v1/agent/investigate` | POST | Start investigation |
| `/api/v1/feeds` | GET | List articles |

See [API Reference](../api/README.md) for full documentation.

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | - | Required for LLM |
| `DATABASE_URL` | - | PostgreSQL connection |
| `AGENT_GDELT_ENABLED` | true | Enable GDELT |
| `AGENT_SCAN_INTERVAL_MINUTES` | 15 | Scan frequency |

See [Configuration](../guides/CONFIGURATION.md) for full list.

### Source Tiers

| Tier | Credibility | Sources |
|------|-------------|---------|
| Tier-1 Govt | 0.99 | USGS, NOAA |
| Tier-1 News | 0.90 | GDELT |
| Tier-2 | 0.75-0.85 | ACLED, Currents |
| Tier-3 | 0.30-0.40 | Reddit, Telegram |

See [Source Tiers](../concepts/SOURCE_TIERS.md) for details.

---

## Related Documentation

- [Architecture](../architecture/README.md) - System design
- [Algorithms](../algorithms/README.md) - Algorithm details
- [Guides](../guides/README.md) - How-to guides
