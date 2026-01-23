# Testing Guide

Comprehensive guide for testing the LiveMap backend.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/                    # Unit tests
│   ├── test_event_verifier.py
│   ├── test_confidence_scorer.py
│   ├── test_cross_source_matcher.py
│   ├── test_deduplication.py
│   └── test_edge_cases.py
├── integration/             # Integration tests
│   └── test_scanner_pipeline.py
├── api/                     # API endpoint tests
│   └── test_agent_endpoints.py
└── (existing tests)
    ├── test_filtering_gates.py
    └── test_significance_criteria.py
```

## Running Tests

### All Tests
```bash
uv run pytest tests/ -v
```

### Specific Test File
```bash
uv run pytest tests/unit/test_event_verifier.py -v
```

### Specific Test
```bash
uv run pytest tests/unit/test_event_verifier.py::TestRuleBasedFilter::test_rule_filter_movie_rejected -v
```

### With Coverage
```bash
uv run pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html  # View coverage report
```

### By Marker
```bash
# Only unit tests
uv run pytest -m unit

# Only integration tests
uv run pytest -m integration

# Skip slow tests
uv run pytest -m "not slow"
```

## Test Markers

| Marker | Description |
|--------|-------------|
| `@pytest.mark.unit` | Unit tests (fast, isolated) |
| `@pytest.mark.integration` | Integration tests (multi-component) |
| `@pytest.mark.api` | API endpoint tests |
| `@pytest.mark.slow` | Slow tests (LLM, external APIs) |
| `@pytest.mark.requires_llm` | Tests needing actual LLM |
| `@pytest.mark.requires_db` | Tests needing database |

## Key Fixtures

### TriggerEvent Factory

```python
def test_something(trigger_event_factory):
    event = trigger_event_factory(
        title="Iran attacks US bases",
        source=TriggerSource.GDELT,
        content="Details about the attack",
    )
    assert event.title == "Iran attacks US bases"
```

### LLM Mocks

```python
# Mock that always returns YES
def test_llm_yes(mock_llm_yes):
    is_event, reason = await verify_event_hybrid(text, mock_llm_yes)
    assert is_event

# Mock that always returns NO
def test_llm_no(mock_llm_no):
    is_event, reason = await verify_event_hybrid(text, mock_llm_no)
    assert not is_event

# Mock that times out
def test_llm_timeout(mock_llm_timeout):
    is_event, reason = await verify_event_hybrid(text, mock_llm_timeout)
    assert "LLM_ERROR" in reason

# Custom response
def test_custom(mock_llm_response):
    mock_llm = mock_llm_response("VERDICT: YES\nREASON: Test")
    result = await verify_event_with_llm(text, mock_llm)
```

### Source Fixtures

```python
# Single sources
def test_single_gdelt(single_gdelt_source):
    result = scorer.calculate_confidence(single_gdelt_source)

def test_single_usgs(single_usgs_source):
    # Tier-1 govt source
    result = scorer.calculate_confidence(single_usgs_source)

# Multi-source
def test_multi(gdelt_plus_reddit_sources):
    result = scorer.calculate_confidence(gdelt_plus_reddit_sources)
    assert result.two_source_satisfied
```

### Sample Text Fixtures

```python
def test_real_events(real_event_texts):
    for text in real_event_texts:
        passed, _ = is_likely_real_event(text)
        assert passed

def test_not_events(not_event_texts):
    for text in not_event_texts:
        passed, _ = is_likely_real_event(text)
        assert not passed

def test_edge_cases(edge_case_texts):
    # Handle empty, unicode, long text, etc.
    for key, text in edge_case_texts.items():
        # Test doesn't crash
        is_likely_real_event(text)
```

## Writing Tests

### Unit Test Template

```python
"""
Unit tests for [Component Name].

Tests:
1. [Test category 1]
2. [Test category 2]
"""

import pytest

from app.agent.module import function_to_test


class TestFunctionName:
    """Tests for function_name."""

    def test_basic_case(self):
        """Basic case should return expected result."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case_empty(self):
        """Empty input should be handled."""
        result = function_to_test("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Async operation should complete."""
        result = await async_function("input")
        assert result


class TestAnotherFeature:
    """Tests for another feature."""

    @pytest.fixture
    def local_fixture(self):
        """Fixture for this test class."""
        return {"key": "value"}

    def test_with_fixture(self, local_fixture):
        """Test using local fixture."""
        assert local_fixture["key"] == "value"
```

### Integration Test Template

```python
"""
Integration tests for [Pipeline/Feature].
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPipelineIntegration:
    """Tests for full pipeline flow."""

    @pytest.fixture
    def mock_scanner(self):
        """Create scanner with mocked components."""
        with patch.object(Scanner, '_create_trigger_manager'):
            scanner = Scanner()
            scanner.trigger_manager = MagicMock()
            scanner.trigger_manager.scan_all = AsyncMock(return_value=[])
            return scanner

    @pytest.mark.asyncio
    async def test_full_flow(self, mock_scanner, trigger_event_factory):
        """Full pipeline should process events correctly."""
        events = [trigger_event_factory(title="Test event")]
        mock_scanner.trigger_manager.scan_all.return_value = events

        result = await mock_scanner.scan()

        assert isinstance(result, list)
```

## Mocking Strategies

### Mock External APIs

```python
@pytest.fixture
def mock_gdelt_api():
    """Mock GDELT API responses."""
    with patch('httpx.AsyncClient.get') as mock:
        mock.return_value.json.return_value = {
            "articles": [{"title": "Test", "url": "http://test.com"}]
        }
        yield mock
```

### Mock LLM Calls

```python
def test_with_mocked_llm(mock_llm_response):
    """Test with controlled LLM response."""
    mock_llm = mock_llm_response("VERDICT: YES\nREASON: Real event")

    result = await verify_event_with_llm("text", mock_llm)

    mock_llm.ainvoke.assert_called_once()
```

### Mock Database

```python
@pytest.fixture
def mock_db_session():
    """Mock async database session."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session
```

## Test Coverage Goals

| Module | Target Coverage |
|--------|-----------------|
| `event_verifier.py` | 90%+ |
| `confidence_scorer.py` | 90%+ |
| `cross_source_matcher.py` | 85%+ |
| `deduplication/` | 85%+ |
| `scanner.py` | 80%+ |
| `triggers/` | 70%+ |
| Overall | 70%+ |

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3

      - name: Install dependencies
        run: uv sync

      - name: Run tests
        run: uv run pytest tests/ -v --cov=app

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

## Debugging Tests

### Verbose Output
```bash
uv run pytest tests/unit/test_event_verifier.py -v -s
```

### Debug with pdb
```bash
uv run pytest tests/unit/test_event_verifier.py --pdb
```

### Show Locals on Failure
```bash
uv run pytest tests/ -l
```

### Run Last Failed
```bash
uv run pytest --lf
```

## Performance Testing

### Measure Test Duration
```bash
uv run pytest tests/ --durations=10
```

### Profile Tests
```bash
uv run pytest tests/unit/test_event_verifier.py --profile
```

## Common Issues

### Async Test Errors
```python
# Wrong: Missing marker
def test_async():
    await something()  # Error!

# Correct: Add marker
@pytest.mark.asyncio
async def test_async():
    await something()
```

### Mock Not Applied
```python
# Wrong: Patching wrong path
with patch('module.function'):  # Patches source, not import

# Correct: Patch where it's used
with patch('app.agent.scanner.function'):  # Patches in scanner
```

### Fixture Not Found
```python
# Make sure conftest.py is in tests/ directory
# Fixtures defined in conftest.py are auto-discovered
```
