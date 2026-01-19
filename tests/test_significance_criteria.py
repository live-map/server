"""
Test script to diagnose why events are being rejected as "not significant".

This script:
1. Fetches events from GDELT
2. Shows exactly what the LLM receives
3. Shows the LLM's response
4. Identifies the criteria gap
"""

import asyncio
import logging
import json
from unittest.mock import patch, AsyncMock

import pytest

# Setup detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_scanner_significance_criteria():
    """
    Test to understand why events are marked as not significant.

    Run with: uv run pytest tests/test_significance_criteria.py::test_scanner_significance_criteria -v -s
    """
    from app.agent.scanner import MultiSourceScanner
    from app.agent.triggers.gdelt import GDELTTrigger

    print("\n" + "=" * 70)
    print("SIGNIFICANCE CRITERIA DIAGNOSTIC TEST")
    print("=" * 70)

    # Step 1: Get raw events from GDELT
    print("\n[STEP 1] Fetching raw events from GDELT...")
    gdelt = GDELTTrigger(timespan="1h", max_results=50)
    await gdelt.initialize()
    raw_events = await gdelt.scan()

    print(f"  Raw events from GDELT: {len(raw_events)}")

    if raw_events:
        print("\n  Sample events (first 5):")
        for i, event in enumerate(raw_events[:5]):
            print(f"    [{i+1}] {event.title[:80]}")
            print(f"        Keywords: {event.keywords_matched}")
            print(f"        Source: {event.source_name}")

    # Step 2: Create scanner and run
    print("\n[STEP 2] Running scanner with LLM classification...")
    scanner = MultiSourceScanner()

    # Enable debug logging for LLM calls
    import logging
    logging.getLogger("app.agent.scanner").setLevel(logging.DEBUG)

    events = await scanner.scan_all_sources()

    print(f"\n[RESULT] Significant events returned: {len(events)}")

    if events:
        print("\n  Significant events:")
        for i, event in enumerate(events):
            print(f"    [{i+1}] {event.get('description', 'N/A')}")
            print(f"        Category: {event.get('category', 'N/A')}")
    else:
        print("\n  ⚠️  NO SIGNIFICANT EVENTS - All events were rejected by LLM")
        print("\n  Events that were rejected:")
        for i, event in enumerate(raw_events[:10]):
            print(f"    [{i+1}] {event.title[:80]}")

    await scanner.close()

    # Analysis
    print("\n" + "=" * 70)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 70)
    print("""
    PROBLEM 1: Keywords are too broad
    - "attack" matches: dingo attacks, bat attacks, cyber attacks
    - "terrorist" matches: political bills mentioning terrorists

    PROBLEM 2: LLM "significance" is undefined
    - Prompt: "Only include breaking/significant events, not routine news"
    - No objective criteria for what makes news "significant"

    PROBLEM 3: No confidence scoring
    - Events are binary (significant or not)
    - Cannot tune sensitivity

    PROBLEM 4: No logging of LLM decisions
    - Cannot debug why events were rejected
    """)

    return {
        "raw_events": len(raw_events),
        "significant_events": len(events),
    }


@pytest.mark.asyncio
async def test_raw_events_without_llm_filter():
    """
    Test to see what events look like WITHOUT LLM filtering.
    This shows what's being rejected.

    Run with: uv run pytest tests/test_significance_criteria.py::test_raw_events_without_llm_filter -v -s
    """
    from app.agent.triggers.gdelt import GDELTTrigger
    from app.agent.triggers.base import TriggerSource

    print("\n" + "=" * 70)
    print("RAW EVENTS TEST (NO LLM FILTER)")
    print("=" * 70)

    gdelt = GDELTTrigger(timespan="1h", max_results=50)
    await gdelt.initialize()
    events = await gdelt.scan()

    print(f"\nTotal events matching keywords: {len(events)}")

    # Group by keyword
    keyword_counts = {}
    for event in events:
        for kw in event.keywords_matched:
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1

    print(f"\nKeyword frequency:")
    for kw, count in sorted(keyword_counts.items(), key=lambda x: -x[1]):
        print(f"  {kw}: {count}")

    print(f"\nAll events:")
    for i, event in enumerate(events):
        print(f"\n[{i+1}] {event.title}")
        print(f"    Keywords: {', '.join(event.keywords_matched)}")
        print(f"    Source: {event.source_name}")
        print(f"    URL: {event.url[:80]}...")

    await gdelt.close()
    return events


@pytest.mark.asyncio
async def test_proposed_deterministic_criteria():
    """
    Test proposed deterministic significance criteria.

    Run with: uv run pytest tests/test_significance_criteria.py::test_proposed_deterministic_criteria -v -s
    """
    from app.agent.triggers.gdelt import GDELTTrigger

    print("\n" + "=" * 70)
    print("PROPOSED DETERMINISTIC CRITERIA TEST")
    print("=" * 70)

    gdelt = GDELTTrigger(timespan="1h", max_results=50)
    await gdelt.initialize()
    events = await gdelt.scan()

    # Proposed scoring system
    HIGH_PRIORITY_KEYWORDS = {
        "war", "invasion", "airstrike", "missile", "bombing",
        "terrorist", "attack", "massacre", "killed", "casualties",
        "breaking", "urgent"
    }

    MEDIUM_PRIORITY_KEYWORDS = {
        "military", "troops", "armed conflict",
        "protest", "riot", "uprising", "unrest",
        "explosion", "violence", "emergency"
    }

    def calculate_significance_score(event) -> int:
        """
        Calculate a deterministic significance score (0-100).

        Criteria:
        - High priority keyword: +20 each (max 60)
        - Medium priority keyword: +10 each (max 30)
        - Multiple keywords: +10 bonus
        - Recent (< 30 min): +10 bonus
        """
        score = 0

        keywords_lower = [kw.lower() for kw in event.keywords_matched]

        # High priority keywords
        high_matches = sum(1 for kw in keywords_lower if kw in HIGH_PRIORITY_KEYWORDS)
        score += min(high_matches * 20, 60)

        # Medium priority keywords
        med_matches = sum(1 for kw in keywords_lower if kw in MEDIUM_PRIORITY_KEYWORDS)
        score += min(med_matches * 10, 30)

        # Multiple keyword bonus
        if len(event.keywords_matched) >= 2:
            score += 10

        return min(score, 100)

    print(f"\nScoring {len(events)} events...")

    scored_events = []
    for event in events:
        score = calculate_significance_score(event)
        scored_events.append((event, score))

    # Sort by score
    scored_events.sort(key=lambda x: -x[1])

    print(f"\nEvents ranked by significance score:")
    print("-" * 70)

    for event, score in scored_events:
        status = "✅ SIGNIFICANT" if score >= 30 else "⚪ LOW"
        print(f"\n[{score:3d}] {status}")
        print(f"      {event.title[:70]}")
        print(f"      Keywords: {', '.join(event.keywords_matched)}")

    significant = [e for e, s in scored_events if s >= 30]
    print(f"\n" + "=" * 70)
    print(f"RESULT: {len(significant)}/{len(events)} events would be significant (threshold: 30)")
    print("=" * 70)

    await gdelt.close()

    return scored_events


if __name__ == "__main__":
    # Run directly
    asyncio.run(test_scanner_significance_criteria())
