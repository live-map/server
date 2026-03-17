"""Admin Controller - Admin-only API endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.dto import IPReportResponse
from app.api.v1.admin.service import AdminService
from app.api.v1.interpreter.jwt_guard import CurrentAdmin
from app.core.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get(
    "/polls/{poll_id}/ip-report",
    response_model=IPReportResponse,
    response_model_by_alias=True,
    summary="IP 기반 부정투표 리포트",
)
async def get_ip_report(
    poll_id: uuid.UUID,
    current_admin: CurrentAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IPReportResponse:
    """
    특정 여론조사의 IP 기반 부정투표 패턴을 조회합니다.

    - 관리자 전용 (ADMIN role 필수)
    - IP는 SHA-256 해시로 제공 (원본 미노출)
    - 동일 IP에서 2명 이상 투표한 경우 '의심' 표시
    """
    service = AdminService(session)
    return await service.get_ip_report(poll_id)
