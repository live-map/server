"""Admin Service - IP report aggregation logic."""

import hashlib
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.dto import IPReportResponse, SuspiciousIPEntry
from app.models.vote import Vote


def hash_ip(ip: str) -> str:
    """IP를 SHA-256 해시로 변환. 원본 노출 방지."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


class AdminService:
    """관리자 전용 비즈니스 로직."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ip_report(self, poll_id: uuid.UUID) -> IPReportResponse:
        """특정 여론조사의 IP 기반 부정투표 리포트 생성."""

        # 전체 투표수
        total_stmt = select(func.count()).where(Vote.poll_id == poll_id)
        total_votes = (await self.session.execute(total_stmt)).scalar_one()

        # 유니크 IP 수 (voter_ip가 NULL이 아닌 것만)
        unique_stmt = select(func.count(func.distinct(Vote.voter_ip))).where(
            Vote.poll_id == poll_id,
            Vote.voter_ip.is_not(None),
        )
        unique_ips = (await self.session.execute(unique_stmt)).scalar_one()

        # 의심 IP: 동일 IP에서 2명 이상의 유저가 투표
        suspicious_stmt = (
            select(
                Vote.voter_ip,
                func.count().label("vote_count"),
                func.count(func.distinct(Vote.user_id)).label("user_count"),
                func.min(Vote.created_at).label("first_vote_at"),
                func.max(Vote.created_at).label("last_vote_at"),
            )
            .where(
                Vote.poll_id == poll_id,
                Vote.voter_ip.is_not(None),
            )
            .group_by(Vote.voter_ip)
            .having(func.count(func.distinct(Vote.user_id)) >= 2)
            .order_by(func.count(func.distinct(Vote.user_id)).desc())
        )
        result = await self.session.execute(suspicious_stmt)
        rows = result.all()

        suspicious_ips = [
            SuspiciousIPEntry(
                ip_hash=hash_ip(row.voter_ip),
                vote_count=row.vote_count,
                user_count=row.user_count,
                first_vote_at=row.first_vote_at,
                last_vote_at=row.last_vote_at,
            )
            for row in rows
        ]

        return IPReportResponse(
            poll_id=poll_id,
            total_votes=total_votes,
            unique_ips=unique_ips,
            suspicious_ips=suspicious_ips,
        )
