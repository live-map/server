"""
투표 쿨다운 단위 테스트.

3초 쿨다운이 적용되어 연타 투표를 방지하는지 검증한다.
"""

import time
from unittest.mock import patch

import pytest

from app.api.v1.poll.vote.service import (
    VOTE_COOLDOWN_SECONDS,
    VoteCooldownError,
    _check_cooldown,
    _set_cooldown,
    _vote_cooldown_cache,
)


@pytest.fixture(autouse=True)
def clear_cooldown_cache():
    """각 테스트 전후로 쿨다운 캐시 초기화."""
    _vote_cooldown_cache.clear()
    yield
    _vote_cooldown_cache.clear()


class TestCooldownCheck:
    """_check_cooldown 함수 테스트."""

    def test_no_previous_vote_returns_none(self):
        """이전 투표 기록이 없으면 None 반환 (통과)."""
        result = _check_cooldown("user-1")
        assert result is None

    def test_cooldown_active_returns_remaining(self):
        """쿨다운 중이면 남은 시간 반환."""
        _set_cooldown("user-1")
        result = _check_cooldown("user-1")
        assert result is not None
        assert 0 < result <= VOTE_COOLDOWN_SECONDS

    def test_cooldown_expired_returns_none(self):
        """쿨다운 시간이 지나면 None 반환 (통과)."""
        # monotonic 시간을 과거로 설정
        _vote_cooldown_cache["user-1"] = time.monotonic() - VOTE_COOLDOWN_SECONDS - 1
        result = _check_cooldown("user-1")
        assert result is None

    def test_different_users_independent(self):
        """유저별로 독립적인 쿨다운."""
        _set_cooldown("user-1")
        assert _check_cooldown("user-1") is not None
        assert _check_cooldown("user-2") is None


class TestSetCooldown:
    """_set_cooldown 함수 테스트."""

    def test_sets_timestamp(self):
        """쿨다운 타이머 설정."""
        _set_cooldown("user-1")
        assert "user-1" in _vote_cooldown_cache

    def test_updates_existing_timestamp(self):
        """기존 타이머 갱신."""
        _set_cooldown("user-1")
        first = _vote_cooldown_cache["user-1"]
        time.sleep(0.01)
        _set_cooldown("user-1")
        second = _vote_cooldown_cache["user-1"]
        assert second > first

    def test_cleanup_expired_entries(self):
        """1000개 초과 시 만료 엔트리 정리."""
        expired_time = time.monotonic() - VOTE_COOLDOWN_SECONDS - 10
        for i in range(1001):
            _vote_cooldown_cache[f"old-user-{i}"] = expired_time

        _set_cooldown("new-user")

        # 만료된 엔트리들이 정리되어야 함
        assert len(_vote_cooldown_cache) < 1001
        assert "new-user" in _vote_cooldown_cache


class TestVoteCooldownError:
    """VoteCooldownError 예외 테스트."""

    def test_remaining_attribute(self):
        """remaining 속성 접근."""
        err = VoteCooldownError(2.5)
        assert err.remaining == 2.5

    def test_error_message(self):
        """에러 메시지 형식."""
        err = VoteCooldownError(2.5)
        assert "2.5" in str(err)


class TestCooldownConstants:
    """쿨다운 상수 검증."""

    def test_cooldown_is_3_seconds(self):
        assert VOTE_COOLDOWN_SECONDS == 3
