# Security Documentation

LiveMap의 보안 가이드라인 및 모범 사례입니다.

---

## Overview

LiveMap은 민감한 API 키를 처리하고 외부 소스의 데이터를 가공합니다. 이 섹션에서는 보안 고려사항을 다룹니다.

---

## Contents

- **[API Keys](API_KEYS.md)** - API 자격 증명을 안전하게 관리하기
- **[Data Handling](DATA_HANDLING.md)** - 데이터 처리 및 저장 방법

---

## Quick Security Checklist

### Development

- [ ] API 키를 `.env` 파일에 저장 (커밋하지 않음)
- [ ] `.env`를 `.gitignore`에 추가
- [ ] 코드에 자격 증명을 하드코딩하지 않음
- [ ] 의존성을 정기적으로 업데이트

### Production

- [ ] 강력한 데이터베이스 비밀번호 사용
- [ ] 모든 엔드포인트에 SSL/TLS 활성화
- [ ] 환경 변수 보안 (로그에 노출되지 않도록)
- [ ] 방화벽 설정 (최소한의 포트만 노출)
- [ ] 정기적인 보안 업데이트
- [ ] 백업 전략 구현
- [ ] Rate limiting 활성화

---

## Reporting Security Issues

보안 취약점을 발견한 경우:

1. 공개 GitHub 이슈를 생성하지 **마세요**
2. 보안 관련 문의는 비공개 이메일로 전달해 주세요
3. 상세한 재현 단계를 제공해 주세요
4. 공개 전 수정할 시간을 주세요

---

## Related Documentation

- [Deployment](../guides/DEPLOYMENT.md) - 운영 환경 보안
- [Configuration](../guides/CONFIGURATION.md) - 보안 설정
