# ADR-005: Bilingual Article Generation

## Status
Accepted

## Context

Our target market includes both English and Korean-speaking users. We needed to decide how to serve both audiences:

1. **Source language**: Most news sources (GDELT, Reuters) are English
2. **Target audiences**: English speakers + Korean speakers
3. **Quality requirements**: Professional-quality articles in both languages
4. **Cost considerations**: Translation/generation costs

Options ranged from post-generation translation to simultaneous bilingual generation.

## Decision

Implement **simultaneous bilingual generation** where articles are generated in both English and Korean in a single LLM call.

### Generation Approach

```python
BILINGUAL_PROMPT = """
Generate a news article in both English and Korean.

Event: {event_summary}
Sources: {sources}

Output Format:
===ENGLISH===
[English article here]

===KOREAN===
[Korean article here (formal 합니다체)]
"""
```

### Korean Style: Formal (합니다체)

Selected formal speech level (합니다체) for Korean because:
- Appropriate for news/journalism
- Conveys professionalism and authority
- Standard in Korean news media
- Avoids overly casual tone (해요체)

### Implementation Structure

```python
@dataclass
class BilingualArticle:
    english_title: str
    english_body: str
    korean_title: str
    korean_body: str
    sources: list[str]
    generated_at: datetime
```

## Consequences

### Positive
- **Single LLM call**: More efficient than two separate calls
- **Consistent content**: Same facts in both languages
- **Native quality**: Generated, not translated (more natural)
- **Cultural adaptation**: Can adjust phrasing for each audience
- **Simultaneous delivery**: Both versions available immediately

### Negative
- **Higher token usage**: ~2x tokens per generation
- **Single point of failure**: Both versions fail together
- **LLM language bias**: Model may favor one language
- **Quality variance**: Korean may occasionally be less natural
- **Harder testing**: Need bilingual reviewers

## Alternatives Considered

### Alternative A: English-Only + Post-Translation
Generate English article, then translate to Korean.

**Rejected because:**
- Translation often sounds unnatural
- Two API calls (generation + translation)
- Translation may lose nuance
- Longer total latency

### Alternative B: Separate Generation Calls
Generate English and Korean in separate LLM calls.

**Rejected because:**
- 2x API calls and costs
- Potential content inconsistency
- Longer total processing time
- More complex error handling

### Alternative C: Korean-Only Generation
Generate only Korean since source is English.

**Rejected because:**
- Excludes English-speaking users
- Limits market reach
- English sources often more complete
- International audience expects English

### Alternative D: User-Selected Language
Generate only requested language on-demand.

**Considered but deferred because:**
- Adds user request latency
- Cache complexity
- May implement later as optimization

## Quality Assurance

### Korean Quality Checks
- Formal speech level (합니다체) consistency
- Proper Korean sentence structure (SOV)
- Appropriate honorifics for subjects
- Korean news terminology

### English Quality Checks
- AP style conventions
- Neutral, objective tone
- Proper attribution
- Active voice preference

## Configuration

```python
# Agent settings
generate_korean: bool = True
korean_style: str = "formal"  # 합니다체 (formal) or 해요체 (informal)
```

## References
- Implementation: `app/agent/bilingual_article_generator.py`
- Article schema: `app/schemas/article.py`
- Project docs: `docs/CODE.md`
