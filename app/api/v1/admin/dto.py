"""Admin DTO schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SuspiciousIPEntry(BaseModel):
    """동일 IP에서 다수 유저가 투표한 의심 항목."""

    model_config = ConfigDict(populate_by_name=True)

    ip_hash: str = Field(alias="ipHash")
    vote_count: int = Field(alias="voteCount")
    user_count: int = Field(alias="userCount")
    first_vote_at: datetime = Field(alias="firstVoteAt")
    last_vote_at: datetime = Field(alias="lastVoteAt")


class IPReportResponse(BaseModel):
    """IP 리포트 응답."""

    model_config = ConfigDict(populate_by_name=True)

    poll_id: uuid.UUID = Field(alias="pollId")
    total_votes: int = Field(alias="totalVotes")
    unique_ips: int = Field(alias="uniqueIPs")
    suspicious_ips: list[SuspiciousIPEntry] = Field(alias="suspiciousIPs")
