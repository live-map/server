"""
Admin IP Report 테스트.

IP 리포트 집계 로직, 해시 변환, 관리자 전용 접근을 검증한다.
"""

import hashlib
import uuid
from datetime import datetime, timezone

import pytest

from app.api.v1.admin.dto import IPReportResponse, SuspiciousIPEntry
from app.api.v1.admin.service import hash_ip


# ============================================================
# IP 해시 변환 테스트
# ============================================================


class TestIPHash:
    """IP 해시 변환 로직을 검증."""

    def test_hash_returns_16_char_hex(self):
        """해시 결과는 16자리 hex string."""
        result = hash_ip("192.168.1.1")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_same_ip_same_hash(self):
        """같은 IP → 같은 해시."""
        assert hash_ip("10.0.0.1") == hash_ip("10.0.0.1")

    def test_different_ip_different_hash(self):
        """다른 IP → 다른 해시."""
        assert hash_ip("10.0.0.1") != hash_ip("10.0.0.2")

    def test_hash_is_sha256_prefix(self):
        """SHA-256 해시의 앞 16자리와 일치."""
        ip = "203.0.113.42"
        expected = hashlib.sha256(ip.encode()).hexdigest()[:16]
        assert hash_ip(ip) == expected

    def test_ipv6_hash(self):
        """IPv6 주소도 정상 해시."""
        result = hash_ip("2001:db8::1")
        assert len(result) == 16


# ============================================================
# DTO 스키마 테스트
# ============================================================


class TestIPReportDTO:
    """응답 DTO가 올바르게 직렬화되는지 검증."""

    def test_suspicious_ip_entry_serialization(self):
        """SuspiciousIPEntry → camelCase JSON."""
        entry = SuspiciousIPEntry(
            ip_hash="a3f2b1c4d5e6f789",
            vote_count=5,
            user_count=3,
            first_vote_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
            last_vote_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
        )
        data = entry.model_dump(by_alias=True)
        assert data["ipHash"] == "a3f2b1c4d5e6f789"
        assert data["voteCount"] == 5
        assert data["userCount"] == 3
        assert "firstVoteAt" in data
        assert "lastVoteAt" in data

    def test_ip_report_response_serialization(self):
        """IPReportResponse → camelCase JSON."""
        poll_id = uuid.uuid4()
        report = IPReportResponse(
            poll_id=poll_id,
            total_votes=150,
            unique_ips=142,
            suspicious_ips=[
                SuspiciousIPEntry(
                    ip_hash="a3f2b1c4d5e6f789",
                    vote_count=5,
                    user_count=3,
                    first_vote_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
                    last_vote_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
                )
            ],
        )
        data = report.model_dump(by_alias=True)
        assert data["pollId"] == poll_id
        assert data["totalVotes"] == 150
        assert data["uniqueIPs"] == 142
        assert len(data["suspiciousIPs"]) == 1

    def test_empty_suspicious_ips(self):
        """의심 IP가 없는 경우."""
        report = IPReportResponse(
            poll_id=uuid.uuid4(),
            total_votes=50,
            unique_ips=50,
            suspicious_ips=[],
        )
        data = report.model_dump(by_alias=True)
        assert data["suspiciousIPs"] == []


# ============================================================
# 관리자 접근 제어 테스트
# ============================================================


class TestAdminAccess:
    """관리자 전용 접근이 올바르게 설정되었는지 검증."""

    def test_endpoint_requires_admin_dependency(self):
        """IP 리포트 엔드포인트가 CurrentAdmin 의존성을 사용하는지 확인."""
        from app.api.v1.admin.controller import get_ip_report
        import inspect

        sig = inspect.signature(get_ip_report)
        param_names = list(sig.parameters.keys())
        assert "current_admin" in param_names

    def test_router_prefix(self):
        """라우터 prefix가 /admin인지 확인."""
        from app.api.v1.admin.controller import router

        assert router.prefix == "/admin"

    def test_endpoint_registered(self):
        """GET /polls/{poll_id}/ip-report 엔드포인트가 등록되었는지 확인."""
        from app.api.v1.admin.controller import router

        routes = [r.path for r in router.routes]
        assert "/admin/polls/{poll_id}/ip-report" in routes
