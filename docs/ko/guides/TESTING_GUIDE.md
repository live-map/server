# Testing Guide

LiveMap 백엔드 테스트를 위한 종합 가이드입니다.

## Test Structure

```
tests/
├── conftest.py              # 공유 fixture
├── unit/                    # 단위 테스트
│   ├── test_event_verifier.py
│   ├── test_confidence_scorer.py
│   ├── test_cross_source_matcher.py
│   ├── test_deduplication.py
│   └── test_edge_cases.py
├── integration/             # 통합 테스트
│   └── test_scanner_pipeline.py
├── api/                     # API 엔드포인트 테스트
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
open htmlcov/index.html  # 커버리지 리포트 보기
```

### By Marker
```bash
# 단위 테스트만 실행
uv run pytest -m unit

# 통합 테스트만 실행
uv run pytest -m integration

# 느린 테스트 건너뛰기
uv run pytest -m "not slow"
```

## Test Markers

| Marker | 설명 |
|--------|------|
| `@pytest.mark.unit` | 단위 테스트 (빠르고 격리됨) |
| `@pytest.mark.integration` | 통합 테스트 (다중 컴포넌트) |
| `@pytest.mark.api` | API 엔드포인트 테스트 |
| `@pytest.mark.slow` | 느린 테스트 (LLM, 외부 API) |
| `@pytest.mark.requires_llm` | 실제 LLM이 필요한 테스트 |
| `@pytest.mark.requires_db` | 데이터베이스가 필요한 테스트 |

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
# 항상 YES를 반환하는 Mock
def test_llm_yes(mock_llm_yes):
    is_event, reason = await verify_event_hybrid(text, mock_llm_yes)
    assert is_event

# 항상 NO를 반환하는 Mock
def test_llm_no(mock_llm_no):
    is_event, reason = await verify_event_hybrid(text, mock_llm_no)
    assert not is_event

# 타임아웃되는 Mock
def test_llm_timeout(mock_llm_timeout):
    is_event, reason = await verify_event_hybrid(text, mock_llm_timeout)
    assert "LLM_ERROR" in reason

# 커스텀 응답
def test_custom(mock_llm_response):
    mock_llm = mock_llm_response("VERDICT: YES\nREASON: Test")
    result = await verify_event_with_llm(text, mock_llm)
```

### Source Fixtures

```python
# 단일 소스
def test_single_gdelt(single_gdelt_source):
    result = scorer.calculate_confidence(single_gdelt_source)

def test_single_usgs(single_usgs_source):
    # Tier-1 정부 소스
    result = scorer.calculate_confidence(single_usgs_source)

# 다중 소스
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
    # 빈 문자열, 유니코드, 긴 텍스트 등 처리
    for key, text in edge_case_texts.items():
        # 테스트가 크래시되지 않음
        is_likely_real_event(text)
```

## Writing Tests

### Unit Test Template

```python
"""
[컴포넌트 이름]에 대한 단위 테스트.

테스트:
1. [테스트 카테고리 1]
2. [테스트 카테고리 2]
"""

import pytest

from app.agent.module import function_to_test


class TestFunctionName:
    """function_name에 대한 테스트."""

    def test_basic_case(self):
        """기본 케이스는 예상 결과를 반환해야 함."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case_empty(self):
        """빈 입력이 처리되어야 함."""
        result = function_to_test("")
        assert result is not None

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """비동기 작업이 완료되어야 함."""
        result = await async_function("input")
        assert result


class TestAnotherFeature:
    """다른 기능에 대한 테스트."""

    @pytest.fixture
    def local_fixture(self):
        """이 테스트 클래스를 위한 fixture."""
        return {"key": "value"}

    def test_with_fixture(self, local_fixture):
        """로컬 fixture를 사용한 테스트."""
        assert local_fixture["key"] == "value"
```

### Integration Test Template

```python
"""
[Pipeline/기능]에 대한 통합 테스트.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestPipelineIntegration:
    """전체 Pipeline 흐름에 대한 테스트."""

    @pytest.fixture
    def mock_scanner(self):
        """Mock된 컴포넌트로 Scanner 생성."""
        with patch.object(Scanner, '_create_trigger_manager'):
            scanner = Scanner()
            scanner.trigger_manager = MagicMock()
            scanner.trigger_manager.scan_all = AsyncMock(return_value=[])
            return scanner

    @pytest.mark.asyncio
    async def test_full_flow(self, mock_scanner, trigger_event_factory):
        """전체 Pipeline이 이벤트를 올바르게 처리해야 함."""
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
    """GDELT API 응답 Mock."""
    with patch('httpx.AsyncClient.get') as mock:
        mock.return_value.json.return_value = {
            "articles": [{"title": "Test", "url": "http://test.com"}]
        }
        yield mock
```

### Mock LLM Calls

```python
def test_with_mocked_llm(mock_llm_response):
    """제어된 LLM 응답으로 테스트."""
    mock_llm = mock_llm_response("VERDICT: YES\nREASON: Real event")

    result = await verify_event_with_llm("text", mock_llm)

    mock_llm.ainvoke.assert_called_once()
```

### Mock Database

```python
@pytest.fixture
def mock_db_session():
    """비동기 데이터베이스 세션 Mock."""
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session
```

## Test Coverage Goals

| 모듈 | 목표 커버리지 |
|------|---------------|
| `event_verifier.py` | 90%+ |
| `confidence_scorer.py` | 90%+ |
| `cross_source_matcher.py` | 85%+ |
| `deduplication/` | 85%+ |
| `scanner.py` | 80%+ |
| `triggers/` | 70%+ |
| 전체 | 70%+ |

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
# 잘못된 예: marker 누락
def test_async():
    await something()  # Error!

# 올바른 예: marker 추가
@pytest.mark.asyncio
async def test_async():
    await something()
```

### Mock Not Applied
```python
# 잘못된 예: 잘못된 경로 패치
with patch('module.function'):  # 소스를 패치, import가 아님

# 올바른 예: 사용되는 곳에서 패치
with patch('app.agent.scanner.function'):  # Scanner에서 패치
```

### Fixture Not Found
```python
# conftest.py가 tests/ 디렉토리에 있는지 확인
# conftest.py에 정의된 fixture는 자동으로 발견됨
```
