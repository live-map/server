"""
Vote Service - Business logic for poll voting.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.poll.repository import PollRepository
from app.api.v1.poll.vote.repository import VoteRepository
from app.models.poll_option import PollOption
from app.models.vote import Vote

logger = logging.getLogger(__name__)


class AlreadyVotedError(Exception):
    """사용자가 이미 투표한 경우."""
    pass


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
    ) -> Vote:
        """
        투표하기. interactionType별로 분기 처리.

        Raises:
            PollNotActiveError: 여론조사가 활성 상태가 아닐 때
            AlreadyVotedError: 이미 투표했을 때
            InvalidOptionError: 유효하지 않은 선택지일 때
        """
        # 여론조사 확인
        poll = await self.poll_repo.get_by_id_with_details(poll_id)
        if poll is None:
            from app.api.v1.poll.service import PollNotFoundError
            raise PollNotFoundError(f"Poll {poll_id} not found")

        if poll.status != "ACTIVE":
            raise PollNotActiveError("이 여론조사는 현재 투표를 받지 않습니다.")

        # 중복 투표 확인
        existing = await self.vote_repo.get_by_user_and_poll(user_id, poll_id)
        if existing:
            raise AlreadyVotedError("이미 투표하셨습니다.")

        # 선택지 ID 세트
        option_ids = {opt.id for opt in poll.options}

        # interactionType별 투표 처리
        vote = Vote(user_id=user_id, poll_id=poll_id)

        if interaction_type in ("BINARY", "SINGLE_CHOICE", "EMOJI_REACTION"):
            if option_id is None or option_id not in option_ids:
                raise InvalidOptionError("유효하지 않은 선택지입니다.")
            vote.option_id = option_id
            # 선택지 투표수 증가
            for opt in poll.options:
                if opt.id == option_id:
                    opt.vote_count += 1
                    break

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
            # 선택된 각 옵션의 투표수 증가
            for opt in poll.options:
                if opt.id in selected_option_ids:
                    opt.vote_count += 1

        elif interaction_type == "RANKING":
            if not ranking_data:
                raise InvalidOptionError("랭킹 데이터가 필요합니다.")
            for oid in ranking_data:
                if oid not in option_ids:
                    raise InvalidOptionError(f"유효하지 않은 선택지: {oid}")
            vote.ranking_data = [str(oid) for oid in ranking_data]
            # 1위 옵션의 투표수 증가 (대표 집계용)
            if ranking_data:
                for opt in poll.options:
                    if opt.id == ranking_data[0]:
                        opt.vote_count += 1
                        break

        # Poll 전체 투표수 증가
        poll.total_votes += 1

        created = await self.vote_repo.create(vote)
        await self.session.commit()
        logger.info(f"Vote cast: user={user_id}, poll={poll_id}, type={interaction_type}")
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
