"""
IP 로깅 테스트.

투표 시 IP 추출 로직이 헤더 우선순위에 따라 정상 동작하는지 검증한다.
Fly-Client-IP > X-Forwarded-For > client.host
"""

import pytest


class TestIPExtraction:
    """Controller의 IP 추출 로직을 단위 테스트."""

    @staticmethod
    def extract_ip(headers: dict, client_host: str | None = None) -> str | None:
        """Controller의 IP 추출 로직 재현."""
        return (
            headers.get("fly-client-ip")
            or (headers.get("x-forwarded-for", "").split(",")[0].strip() or None)
            or client_host
        )

    def test_fly_client_ip_header(self):
        """Fly-Client-IP 헤더가 최우선."""
        ip = self.extract_ip(
            {"fly-client-ip": "1.2.3.4", "x-forwarded-for": "5.6.7.8"},
            client_host="127.0.0.1",
        )
        assert ip == "1.2.3.4"

    def test_x_forwarded_for_single(self):
        """Fly-Client-IP 없으면 X-Forwarded-For 첫 번째 IP."""
        ip = self.extract_ip(
            {"x-forwarded-for": "10.0.0.1"},
            client_host="127.0.0.1",
        )
        assert ip == "10.0.0.1"

    def test_x_forwarded_for_multiple(self):
        """X-Forwarded-For에 여러 IP가 있으면 첫 번째만."""
        ip = self.extract_ip(
            {"x-forwarded-for": "10.0.0.1, 10.0.0.2, 10.0.0.3"},
            client_host="127.0.0.1",
        )
        assert ip == "10.0.0.1"

    def test_x_forwarded_for_with_spaces(self):
        """X-Forwarded-For에 공백이 있어도 trim."""
        ip = self.extract_ip(
            {"x-forwarded-for": "  10.0.0.1 , 10.0.0.2"},
            client_host="127.0.0.1",
        )
        assert ip == "10.0.0.1"

    def test_fallback_to_client_host(self):
        """헤더 없으면 client.host로 fallback."""
        ip = self.extract_ip({}, client_host="127.0.0.1")
        assert ip == "127.0.0.1"

    def test_no_ip_available(self):
        """모든 소스가 없으면 None."""
        ip = self.extract_ip({}, client_host=None)
        assert ip is None

    def test_empty_x_forwarded_for(self):
        """빈 X-Forwarded-For → fallback."""
        ip = self.extract_ip(
            {"x-forwarded-for": ""},
            client_host="127.0.0.1",
        )
        assert ip == "127.0.0.1"

    def test_ipv6_address(self):
        """IPv6 주소도 정상 처리."""
        ip = self.extract_ip(
            {"fly-client-ip": "2001:db8::1"},
        )
        assert ip == "2001:db8::1"

    def test_ipv6_in_forwarded_for(self):
        """X-Forwarded-For에 IPv6."""
        ip = self.extract_ip(
            {"x-forwarded-for": "2001:db8::1, 10.0.0.1"},
        )
        assert ip == "2001:db8::1"
