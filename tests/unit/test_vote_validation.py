"""
투표 검증 로직 단위 테스트.

P1-5 (카운터 순서), P1-7 (Slider 범위), P1-8 (Ranking 유일성/완전성) 검증.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.poll.vote.service import (
    InvalidOptionError,
    VoteService,
    _vote_cooldown_cache,
)


@pytest.fixture(autouse=True)
def clear_cooldown_cache():
    """각 테스트 전후로 쿨다운 캐시 초기화."""
    _vote_cooldown_cache.clear()
    yield
    _vote_cooldown_cache.clear()


def _make_option(option_id: uuid.UUID | None = None) -> MagicMock:
    """테스트용 PollOption mock 생성."""
    opt = MagicMock()
    opt.id = option_id or uuid.uuid4()
    return opt


def _make_poll(interaction_type: str, options: list[MagicMock], status: str = "ACTIVE") -> MagicMock:
    """테스트용 Poll mock 생성."""
    poll = MagicMock()
    poll.id = uuid.uuid4()
    poll.status = status
    poll.interaction_type = interaction_type
    poll.options = options
    return poll


@pytest.fixture
def session():
    """Mock AsyncSession."""
    s = AsyncMock()
    s.execute = AsyncMock()
    s.flush = AsyncMock()
    s.commit = AsyncMock()
    s.rollback = AsyncMock()
    return s


@pytest.fixture
def service(session):
    """VoteService with mocked dependencies."""
    svc = VoteService(session)
    svc.vote_repo = AsyncMock()
    svc.poll_repo = AsyncMock()
    return svc


class TestSliderValidation:
    """P1-7: Slider 범위 검증 (service 레이어)."""

    @pytest.mark.asyncio
    async def test_slider_value_below_zero_rejected(self, service):
        """슬라이더 값 < 0이면 InvalidOptionError."""
        options = [_make_option()]
        poll = _make_poll("SLIDER", options)
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)

        with pytest.raises(InvalidOptionError, match="0~100"):
            await service.cast_vote(
                user_id="user-1", poll_id=poll.id,
                interaction_type="SLIDER", slider_value=-1,
            )

    @pytest.mark.asyncio
    async def test_slider_value_above_100_rejected(self, service):
        """슬라이더 값 > 100이면 InvalidOptionError."""
        options = [_make_option()]
        poll = _make_poll("SLIDER", options)
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)

        with pytest.raises(InvalidOptionError, match="0~100"):
            await service.cast_vote(
                user_id="user-1", poll_id=poll.id,
                interaction_type="SLIDER", slider_value=101,
            )

    @pytest.mark.asyncio
    async def test_slider_boundary_values_accepted(self, service):
        """슬라이더 값 0, 100은 허용."""
        options = [_make_option()]
        poll = _make_poll("SLIDER", options)
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)
        service.vote_repo.create = AsyncMock(return_value=MagicMock())

        for value in [0, 50, 100]:
            await service.cast_vote(
                user_id=f"user-{value}", poll_id=poll.id,
                interaction_type="SLIDER", slider_value=value,
            )


class TestRankingValidation:
    """P1-8: Ranking 유일성/완전성 검증."""

    @pytest.mark.asyncio
    async def test_ranking_incomplete_rejected(self, service):
        """모든 선택지를 포함하지 않으면 InvalidOptionError."""
        opt1, opt2, opt3 = _make_option(), _make_option(), _make_option()
        poll = _make_poll("RANKING", [opt1, opt2, opt3])
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)

        with pytest.raises(InvalidOptionError, match="모든 선택지"):
            await service.cast_vote(
                user_id="user-1", poll_id=poll.id,
                interaction_type="RANKING",
                ranking_data=[opt1.id, opt2.id],  # opt3 누락
            )

    @pytest.mark.asyncio
    async def test_ranking_duplicate_rejected(self, service):
        """중복 선택지가 있으면 InvalidOptionError."""
        opt1, opt2 = _make_option(), _make_option()
        poll = _make_poll("RANKING", [opt1, opt2])
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)

        with pytest.raises(InvalidOptionError, match="중복"):
            await service.cast_vote(
                user_id="user-1", poll_id=poll.id,
                interaction_type="RANKING",
                ranking_data=[opt1.id, opt1.id],  # 중복
            )

    @pytest.mark.asyncio
    async def test_ranking_invalid_option_rejected(self, service):
        """유효하지 않은 선택지가 있으면 InvalidOptionError."""
        opt1, opt2 = _make_option(), _make_option()
        poll = _make_poll("RANKING", [opt1, opt2])
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)

        fake_id = uuid.uuid4()
        with pytest.raises(InvalidOptionError, match="유효하지 않은"):
            await service.cast_vote(
                user_id="user-1", poll_id=poll.id,
                interaction_type="RANKING",
                ranking_data=[opt1.id, fake_id],
            )

    @pytest.mark.asyncio
    async def test_ranking_valid_accepted(self, service):
        """올바른 랭킹 데이터 허용."""
        opt1, opt2 = _make_option(), _make_option()
        poll = _make_poll("RANKING", [opt1, opt2])
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)
        service.vote_repo.create = AsyncMock(return_value=MagicMock())

        await service.cast_vote(
            user_id="user-1", poll_id=poll.id,
            interaction_type="RANKING",
            ranking_data=[opt2.id, opt1.id],
        )


class TestVoteCreationOrder:
    """P1-5: 투표 생성이 카운터 증가보다 먼저 실행되는지 검증."""

    @pytest.mark.asyncio
    async def test_create_called_before_increment(self, service):
        """vote_repo.create()가 session.execute(UPDATE) 전에 호출되어야 함."""
        opt = _make_option()
        poll = _make_poll("SINGLE_CHOICE", [opt])
        service.poll_repo.get_by_id_with_details = AsyncMock(return_value=poll)
        service.vote_repo.get_by_user_and_poll = AsyncMock(return_value=None)
        service.vote_repo.create = AsyncMock(return_value=MagicMock())

        call_order = []
        original_create = service.vote_repo.create

        async def tracked_create(vote):
            call_order.append("create")
            return await original_create(vote)

        async def tracked_execute(stmt):
            call_order.append("execute")

        service.vote_repo.create = tracked_create
        service.session.execute = tracked_execute

        await service.cast_vote(
            user_id="user-1", poll_id=poll.id,
            interaction_type="SINGLE_CHOICE", option_id=opt.id,
        )

        # create가 execute들보다 먼저 호출되어야 함
        assert call_order[0] == "create"
        assert all(c == "execute" for c in call_order[1:])
