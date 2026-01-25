# Embedding Model Research

## Overview

Research on alternative embedding models for improving cross-source matching and semantic similarity calculations.

---

## Current Implementation

**Model:** BGE-M3 (BAAI)
**Dimension:** 1024
**Performance:** Good multilingual support, reasonable speed

---

## Alternative Models to Evaluate

### 1. Voyage-3.5 (Voyage AI)

**Status:** Recommended for testing

| Aspect | Details |
|--------|---------|
| Dimension | 1024 |
| Languages | 100+ |
| Context | 32K tokens |
| Cost | $0.02 per 1M tokens |
| Performance | SOTA on MTEB (2024) |

**Advantages:**
- Best-in-class retrieval performance
- Long context window (32K)
- Strong multilingual support
- Commercial API with SLA

**Disadvantages:**
- External API dependency
- Cost per request
- Latency vs local model

**Recommendation:** Test for high-priority verification tasks where accuracy is critical.

---

### 2. E5-Mistral-7B-Instruct

**Status:** Consider for future

| Aspect | Details |
|--------|---------|
| Dimension | 4096 |
| Languages | Multilingual |
| Context | 8K tokens |
| Cost | Self-hosted |
| Performance | Near-SOTA on MTEB |

**Advantages:**
- Instruction-following capability
- High quality embeddings
- Self-hosted (no API cost)

**Disadvantages:**
- Large model (7B parameters)
- Requires GPU for reasonable speed
- Higher memory requirements

**Recommendation:** Consider for batch processing where latency is not critical.

---

### 3. GTE-Qwen2-7B-Instruct

**Status:** Monitor

| Aspect | Details |
|--------|---------|
| Dimension | 3584 |
| Languages | Multilingual (Chinese focus) |
| Context | 8K tokens |
| Cost | Self-hosted |
| Performance | Top-tier on MTEB |

**Advantages:**
- Excellent Chinese support
- Open source
- Instruction-following

**Disadvantages:**
- Large model
- Chinese-centric training
- Resource intensive

**Recommendation:** Monitor for Asian language coverage improvement.

---

### 4. mxbai-embed-large-v1

**Status:** Good alternative

| Aspect | Details |
|--------|---------|
| Dimension | 1024 |
| Languages | Multilingual |
| Context | 512 tokens |
| Cost | Self-hosted |
| Performance | Competitive on MTEB |

**Advantages:**
- Same dimension as current (easy swap)
- Apache 2.0 license
- Efficient inference

**Disadvantages:**
- Shorter context (512)
- Less multilingual coverage than BGE-M3

**Recommendation:** Test as potential BGE-M3 replacement for speed improvements.

---

## Benchmark Comparison

### MTEB Retrieval Benchmark (2024-Q4)

| Model | Average Score | News Domain | Speed |
|-------|---------------|-------------|-------|
| Voyage-3.5 | 0.692 | 0.71 | Slow (API) |
| E5-Mistral-7B | 0.681 | 0.68 | Slow |
| BGE-M3 (current) | 0.657 | 0.66 | Fast |
| mxbai-embed-large | 0.654 | 0.65 | Fast |
| GTE-Qwen2-7B | 0.678 | 0.67 | Slow |

### Latency Comparison

| Model | Batch (100 texts) | Single text |
|-------|-------------------|-------------|
| BGE-M3 | 2.1s | 25ms |
| mxbai-embed-large | 1.8s | 22ms |
| Voyage-3.5 | 3.5s (API) | 150ms |
| E5-Mistral-7B | 15s (GPU) | 180ms |

---

## Cost Analysis

### Current (BGE-M3, self-hosted)

```
Events/day: 1000
Embeddings/event: 2 (title + content)
Total embeddings: 2000/day

Cost: $0 (self-hosted)
GPU memory: 2GB
Latency: 25ms/embedding
```

### Voyage-3.5 (API)

```
Events/day: 1000
Tokens/embedding: ~500
Total tokens: 1M/day

Cost: $0.02/day
Latency: 150ms/embedding
```

### E5-Mistral-7B (self-hosted)

```
Events/day: 1000
GPU requirement: A10G (24GB)

Cost: ~$2/day (cloud GPU)
Latency: 180ms/embedding
```

---

## Recommendations

### Immediate (Q1 2026)

1. **A/B test Voyage-3.5** for critical verification tasks
2. **Benchmark mxbai-embed-large** as BGE-M3 replacement
3. **Keep BGE-M3 as default** for cost efficiency

### Medium-term (Q2 2026)

1. **Evaluate E5-Mistral-7B** for batch processing
2. **Consider hybrid approach**: Fast model for initial, accurate model for verification
3. **Monitor GTE-Qwen2** for Asian market expansion

### Long-term (2027+)

1. **Custom fine-tuned model** on news verification data
2. **Distilled models** for edge deployment
3. **Multi-vector representations** for improved recall

---

## Testing Protocol

### Metrics to Evaluate

1. **Retrieval accuracy**: Precision@10, Recall@10
2. **Cross-source matching**: Precision of same-event detection
3. **Latency**: P50, P95, P99
4. **Cost**: Per-1000 embeddings
5. **Multilingual**: Performance across languages

### Test Dataset

- 1000 verified event pairs (same event, different sources)
- 1000 negative pairs (different events)
- Coverage: English, Korean, Arabic, Chinese

---

## References

- MTEB Benchmark: https://huggingface.co/spaces/mteb/leaderboard
- Voyage AI: https://www.voyageai.com/
- BGE-M3: https://huggingface.co/BAAI/bge-m3
- E5-Mistral: https://huggingface.co/intfloat/e5-mistral-7b-instruct
