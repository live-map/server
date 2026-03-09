"""
Vote Service - Business logic for poll voting.
"""

import logging
import time
import uuid

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.poll.repository import PollRepository
from app.api.v1.poll.service import PollNotFoundError
from app.api.v1.poll.vote.repository import VoteRepository
from app.models.poll import Poll
from app.models.poll_option import PollOption
from app.models.vote import Vote

logger = logging.getLogger(__name__)

VOTE_COOLDOWN_SECONDS = 3

# In-memory cooldown cache: user_id -> last vote timestamp
_vote_cooldown_cache: dict[str, float] = {}


def _check_cooldown(user_id: str) -> float | None:
    """쿨다운 체크. 남은 시간(초) 반환. None이면 통과."""
    now = time.monotonic()
    last_vote = _vote_cooldown_cache.get(user_id)
    if last_vote is not None:
        elapsed = now - last_vote
        if elapsed < VOTE_COOLDOWN_SECONDS:
            return VOTE_COOLDOWN_SECONDS - elapsed
    return None


def _set_cooldown(user_id: str) -> None:
    """쿨다운 타이머 설정."""
    _vote_cooldown_cache[user_id] = time.monotonic()
    # 오래된 엔트리 정리 (1000개 초과 시)
    if len(_vote_cooldown_cache) > 1000:
        now = time.monotonic()
        expired = [k for k, v in _vote_cooldown_cache.items() if now - v > VOTE_COOLDOWN_SECONDS]
        for k in expired:
            del _vote_cooldown_cache[k]


class AlreadyVotedError(Exception):
    """사용자가 이미 투표한 경우."""
    pass


class VoteCooldownError(Exception):
    """투표 쿨다운 중인 경우."""
    def __init__(self, remaining: float) -> None:
        self.remaining = remaining
        super().__init__(f"투표 쿨다운 중입니다. {remaining:.1f}초 후 다시 시도해주세요.")


class InvalidOptionError(Exception):
    """유효하지 않은 선택지인 경우."""
    pass


class PollNotActiveError(Exception):
    """여론조사가 활성 상태가 아닌 경우."""
    pass


class VoteService:
    """Vote 관련 비즈니스 로직."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.vote_repo = VoteRepository(session)
        self.poll_repo = PollRepository(session)

    async def cast_vote(
        self,
        user_id: str,
        poll_id: uuid.UUID,
        interaction_type: str,
        option_id: uuid.UUID | None = None,
        slider_value: int | None = None,
        selected_option_ids: list[uuid.UUID] | None = None,
        ranking_data: list[uuid.UUID] | None = None,
        voter_ip: str | None = None,
    ) -> Vote:
        """
        투표하기. interactionType별로 분기 처리.

        Raises:
            PollNotActiveError: 여론조사가 활성 상태가 아닐 때
            AlreadyVotedError: 이미 투표했을 때
            InvalidOptionError: 유효하지 않은 선택지일 때
        """
        # 쿨다운 체크
        remaining = _check_cooldown(user_id)
        if remaining is not None:
            raise VoteCooldownError(remaining)

        # 여론조사 확인
        poll = await self.poll_repo.get_by_id_with_details(poll_id)
        if poll is None:
            raise PollNotFoundError(f"Poll {poll_id} not found")

        if poll.status != "ACTIVE":
            raise PollNotActiveError("이 여론조사는 현재 투표를 받지 않습니다.")

        # interaction_type 검증: 클라이언트 요청과 poll 설정 일치 확인
        if poll.interaction_type != interaction_type:
            raise InvalidOptionError(
                f"이 여론조사의 투표 방식은 {poll.interaction_type}입니다."
            )

        # 중복 투표 확인
        existing = await self.vote_repo.get_by_user_and_poll(user_id, poll_id)
        if existing:
            raise AlreadyVotedError("이미 투표하셨습니다.")

        # 선택지 ID 세트
        option_ids = {opt.id for opt in poll.options}

        # interactionType별 투표 처리
        vote = Vote(user_id=user_id, poll_id=poll_id, voter_ip=voter_ip)

        # 원자적 증가 대상 option_id 목록
        increment_option_ids: list[uuid.UUID] = []

        if interaction_type in ("BINARY", "SINGLE_CHOICE", "EMOJI_REACTION"):
            if option_id is None or option_id not in option_ids:
                raise InvalidOptionError("유효하지 않은 선택지입니다.")
            vote.option_id = option_id
            increment_option_ids.append(option_id)

        elif interaction_type == "SLIDER":
            if slider_value is None:
                raise InvalidOptionError("슬라이더 값이 필요합니다.")
            vote.slider_value = slider_value

        elif interaction_type == "MULTIPLE_CHOICE":
            if not selected_option_ids:
                raise InvalidOptionError("하나 이상의 선택지를 골라야 합니다.")
            for oid in selected_option_ids:
                if oid not in option_ids:
                    raise InvalidOptionError(f"유효하지 않은 선택지: {oid}")
            vote.selected_option_ids = [str(oid) for oid in selected_option_ids]
            increment_option_ids.extend(selected_option_ids)

        elif interaction_type == "RANKING":
            if not ranking_data:
                raise InvalidOptionError("랭킹 데이터가 필요합니다.")
            for oid in ranking_data:
                if oid not in option_ids:
                    raise InvalidOptionError(f"유효하지 않은 선택지: {oid}")
            vote.ranking_data = [str(oid) for oid in ranking_data]
            # 1위 옵션의 투표수 증가 (대표 집계용)
            if ranking_data:
                increment_option_ids.append(ranking_data[0])

        # 원자적 옵션 투표수 증가 (SQL UPDATE)
        for oid in increment_option_ids:
            stmt = (
                update(PollOption)
                .where(PollOption.id == oid)
                .values(vote_count=PollOption.vote_count + 1)
            )
            await self.session.execute(stmt)

        # 원자적 Poll 전체 투표수 증가 (SQL UPDATE)
        stmt = (
            update(Poll)
            .where(Poll.id == poll_id)
            .values(total_votes=Poll.total_votes + 1)
        )
        await self.session.execute(stmt)

        try:
            created = await self.vote_repo.create(vote)
            await self.session.commit()
        except IntegrityError:
            await self.session.rollback()
            raise AlreadyVotedError("이미 투표하셨습니다.")

        _set_cooldown(user_id)
        logger.info("Vote cast: user=%s, poll=%s, type=%s", user_id, poll_id, interaction_type)
        return created

    async def get_user_vote(
        self, user_id: str, poll_id: uuid.UUID
    ) -> Vote | None:
        """사용자의 투표 조회."""
        return await self.vote_repo.get_by_user_and_poll(user_id, poll_id)

    async def get_user_vote_status_for_polls(
        self, user_id: str, poll_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, Vote]:
        """여러 여론조사에 대한 사용자 투표 상태."""
        votes = await self.vote_repo.get_user_votes_for_polls(user_id, poll_ids)
        return {vote.poll_id: vote for vote in votes}

    async def get_average_slider_value(self, poll_id: uuid.UUID) -> float | None:
        """SLIDER 타입 poll의 평균 슬라이더 값."""
        return await self.vote_repo.get_average_slider_value(poll_id)
