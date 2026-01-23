# LiveMap Value Proposition

## Core Value

**"Real-time verified international news at 1/1000th the cost"**

---

## Problem Space

### Current Market Pain Points

| Problem | Who Suffers | Cost of Problem |
|---------|-------------|-----------------|
| Slow news detection | Financial institutions, media companies | Missed opportunities, delayed response |
| Unverified information | Everyone | Misinformation spreads, erodes trust |
| Expensive intelligence tools | SMBs, researchers, journalists | $20K-$200K/year for enterprise tools |
| Black-box algorithms | Users who need transparency | No way to audit or trust results |

---

## Our Solution

### Key Differentiators

#### 1. Zero Source Cost

| Competitor | Source Cost | Our Cost |
|------------|-------------|----------|
| Dataminr | Proprietary firehose ($$$) | $0 |
| Bloomberg Terminal | Licensed feeds ($$$) | $0 |
| Traditional newsrooms | Wire services ($50K+/year) | $0 |

**How**: We use entirely free, public data sources:
- [GDELT Project](https://www.gdeltproject.org/) - 100,000+ news sources
- [USGS](https://earthquake.usgs.gov/) / [NOAA](https://www.noaa.gov/) - Government data
- Reddit, Bluesky - Social signals

#### 2. Multi-Source Verification

Unlike single-source platforms, we require **2+ independent sources** before publication.

```
Event Detection → Cross-Source Matching → Two-Source Verification → Publication
       ↓                    ↓                      ↓                    ↓
    Any source         Find same event         Verify with 2+      Publish with
    can detect         across sources          sources              confidence score
```

**Result**: Lower false positive rate than single-source competitors.

#### 3. Transparent Confidence Scoring

Every article shows exactly **why** we trust it:

| Confidence Level | Sources | Score | Example |
|------------------|---------|-------|---------|
| Very High | USGS/NOAA | 0.99 | Earthquake alert |
| High | 2+ Tier-1 news | 0.85+ | Reuters + AP report same event |
| Publishable | Tier-1 news | 0.70+ | Single GDELT article |
| Signal only | Social media | 0.45 | Reddit post (not published) |

#### 4. AI-Powered Cost Efficiency

**3-Stage Verification Pipeline**:
1. **Rules** (free): Filter 70% of non-events
2. **Zero-shot ML** (free): Local model classifies 20% more
3. **LLM** (paid): Only 10% of events need API calls

**Cost comparison**:
| Approach | Cost/day |
|----------|----------|
| LLM-only | $16.13 |
| Rules + LLM | $4.80 |
| **Rules + ML + LLM** | **$1.44** |

---

## Value by User Segment

### For Financial Institutions

| Value | Benefit |
|-------|---------|
| Real-time detection | Trade on breaking news faster |
| Verified information | Reduce risk from false signals |
| 99% cost reduction | $200/month vs $200,000/year |

### For Media Companies

| Value | Benefit |
|-------|---------|
| 15-minute detection | Beat competitors to breaking news |
| Multi-source verification | Reduce editorial workload |
| Transparent methodology | Build reader trust |

### For Researchers

| Value | Benefit |
|-------|---------|
| Free access to verified data | No subscription costs |
| Open methodology | Reproducible research |
| API access | Integrate with research workflows |

### For General Public

| Value | Benefit |
|-------|---------|
| Ad-free experience | No commercial bias |
| Verified news only | No misinformation |
| Confidence scores | Know how trustworthy each article is |

---

## Competitive Moat

### Technical Advantages

1. **Multi-source pipeline**: Complex to replicate integration of 14+ sources
2. **Verification algorithm**: Proprietary confidence scoring tuned over time
3. **SOTA claim verification**: Based on 2026 research (VeriScore, AIC CTU methods)
4. **Cost structure**: Near-zero marginal cost per article

### Network Effects

1. More users → Better feedback → Better verification
2. More sources integrated → Higher accuracy → More trust
3. Open methodology → Community contributions → Continuous improvement

---

## Summary

| Dimension | Competitors | LiveMap |
|-----------|-------------|---------|
| Cost | $20K-$200K/year | ~$200/month |
| Speed | 15-60 min lag | Real-time |
| Verification | Manual or none | Automated multi-source |
| Transparency | Black box | Open methodology |
| Bias | Editorial/algorithmic | Algorithm-based, neutral |

**Bottom line**: LiveMap delivers enterprise-grade news intelligence at consumer prices, with unprecedented transparency and verification.

---

*Related documents:*
- [Investor Summary](INVESTOR_SUMMARY.md)
- [Competitive Analysis](COMPETITIVE_ANALYSIS.md)
- [Overview](../OVERVIEW.md)
