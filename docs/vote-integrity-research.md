# 1인 1투표 신뢰성 확보 연구 보고서

> Grapoll 플랫폼의 투표 무결성을 위한 방어 수단 종합 연구

---

## 1. 현재 시스템 취약점 분석

### 현재 구현

- `UniqueConstraint("user_id", "poll_id")` on votes 테이블
- OAuth(Google/Kakao) 기반 인증
- 비로그인 투표: `f"anon-{uuid.uuid4()}"` 매번 새 UUID (테스트용, DB에 안 남음)

### 핵심 취약점

1. **다계정 공격**: Google/Kakao 다계정 생성으로 무제한 투표 가능
2. **IP 우회**: VPN/프록시로 IP 추적 회피
3. **봇 자동화**: 자동화 투표에 무방비
4. **FK 미설정**: votes.user_id에 users FK 없음

---

## 2. 방어 수단 종합 연구

### A. 본인 인증 (Korean Identity Verification)

#### CI/DI 개념

- **CI (Connection Info)**: 주민번호 암호화 88바이트, 전 기관 동일값 → 기관간 동일인 식별
- **DI (Duplication Info)**: CI + 기관코드 암호화 64바이트, 기관별 고유값 → 서비스 내 중복 방지
- Grapoll은 **DI만으로 충분** (개인정보 최소 수집 원칙)

#### 서비스 비교

| 인증 방법 | 비용 | UX | 효과성 | 구현 난이도 |
|-----------|------|-----|--------|-----------|
| 통신사 본인인증 (NICE/KCB) | 300~600원/건 | 마찰 높음 (팝업, SMS) | 매우 높음 (CI/DI) | 중~높음 (사업자등록 필요, 1~2주 심사) |
| 카카오인증 (BaroCert) | 40~100원/건 | 매우 좋음 (앱 인증) | 매우 높음 (DI) | 중간 (Python SDK 제공) |
| 네이버인증 (BaroCert) | 40~100원/건 | 좋음 | 매우 높음 (DI) | 중간 |
| 토스인증 (BaroCert) | 40~100원/건 | 매우 좋음 | 매우 높음 (DI) | 중간 |
| PASS 앱 (통신3사) | 100~200원/건 | 좋음 | 매우 높음 (DI) | 중간 |
| 공동인증서 | 무료 + 개발비 | 매우 나쁨 | 매우 높음 | 높음, 비권장 |

**통합 연동 플랫폼**: [BaroCert](https://www.barocert.com/) - 카카오/네이버/토스를 하나의 API로, Python SDK 제공, 테스트 무료

### B. 전화번호 인증 (SMS OTP)

| 서비스 | 단문(SMS) 비용 | 특징 |
|--------|-------------|------|
| Aligo | 8.4원/건 | 최저가, REST API |
| NHN Cloud SMS | 9.9원/건 | 안정적, 클라우드 통합 |
| CoolSMS | 20원/건 | 개발자 친화적 |
| Twilio Verify | ~65원/건 | 글로벌, VoIP 번호 자동 차단 |

**한계**: 한국은 선불폰 본인인증 필수이나 대포폰 존재. 1인 다번호(010 2개 이상) 가능.
**효과**: 캐주얼 조작 방지에 높음, 전문 조작에는 중간.

### C. 기기/브라우저 핑거프린팅

| 버전 | 정확도 | 비용 |
|------|--------|------|
| FingerprintJS 오픈소스 v4 | 40~60% | 무료 |
| Fingerprint Pro | 99.5% | Free 1,000건/월, Pro Plus $99/월(20K건) |

**기술 요소**: Canvas, WebGL, AudioContext, Screen, Timezone, Font 등

**한계**: 시크릿모드, 브라우저 변경, 공유기기(PC방) 오탐, Anti-fingerprint 브라우저

**법률**: 개인정보보호법상 사전 동의(opt-in) 필요, 개인정보처리방침 명시

### D. VPN/프록시 탐지

| 서비스 | 정확도 | 무료 티어 | 유료 |
|--------|--------|-----------|------|
| IPQualityScore | 99.95% | 1,000건/월 | $99/월(5K건) |
| MaxMind GeoIP2 | 높음 | GeoLite2 무료 | $288/년~ |
| ip2proxy | 높음 | 무료 DB | $499/년~ |
| Cloudflare (통합) | 높음 | 무료 기본 | - |

**IPQualityScore Fraud Score**: 0~25 정상, 75+ VPN 의심, 85+ 차단 권장

**주의**: 회사/학교 네트워크 오탐 가능, 합법적 VPN 사용자 차단 논란

### E. 봇/자동화 방지

| 솔루션 | 무료 티어 | UX | 비용 |
|--------|-----------|-----|------|
| **Cloudflare Turnstile** | **100만건/월** | **최고 (투명)** | **무료** |
| reCAPTCHA v3 | 1만건/월 (2025 축소) | 좋음 | 유료 |
| hCaptcha | 제한적 | 보통 (이미지) | Enterprise $155K/년 |
| ALTCHA (PoW) | 셀프호스트 무료 | 좋음 | 무료(오픈소스) |

**행동 분석**: 마우스 궤적, 클릭 패턴, 키 입력 간격으로 봇 vs 인간 판별

**Rate Limiting 고도화**: IP당 투표속도 제한, 페이지로드 후 최소 3초 간격 강제

### F. 계정 연결 분석

- **IP 클러스터링**: 동일 IP에서 3+ 다른 user_id 투표 시 플래깅 (NAT 고려)
- **이메일 정규화**: Gmail alias(`+tag`), 점(`.`) 제거 후 중복 체크
- **가입 패턴**: 짧은 시간 대량 가입 + 특정 투표 집중 = 조직적 조작 의심

### G. 통계적 이상 탐지

- **시계열 분석**: 투표 속도 급변 감지 (Z-score +-3 표준편차)
- **Benford 법칙**: 투표 수 첫째 자릿수 분포 검증
- **ML 모델**: Isolation Forest로 이상 투표 패턴 탐지

---

## 3. 계층적 방어 모델 (Defense in Depth) - 권장 전략

### Tier 1: 기본 방어 (즉시 적용, 비용 0원)

| 조치 | 구현 내용 |
|------|----------|
| 로그인 필수화 | 투표 시 OAuth 인증 필수 (anon-UUID 투표 제거) |
| Rate Limiting | IP당 투표 속도 제한 (5분 내 3회) |
| 투표 시간 간격 | 페이지 로드 후 최소 3초 경과 검증 |
| 이메일 정규화 | Gmail alias/dot 중복 체크 |
| IP 로깅 | 투표 시 IP 기록, 동일 IP 다계정 모니터링 |

### Tier 2: 중급 방어 (1~2주, 월 ~$180/24만원)

| 조치 | 비용 |
|------|------|
| Cloudflare Turnstile | 무료 (100만건/월) |
| Fingerprint Pro | $99/월 (20K건) |
| SMS 인증 (Aligo) | ~8.4원/건 |
| 통계 이상 탐지 대시보드 | 자체 개발 |

### Tier 3: 고급 방어 (중요 투표 전용, 월 $500~1,500)

| 조치 | 비용 |
|------|------|
| 본인인증 DI (BaroCert 간편인증) | 40~100원/건 |
| VPN 탐지 (IPQualityScore) | $99~999/월 |
| 행동 분석 | 자체 개발 |
| 종합 Fraud Score | 자체 개발 |

---

## 4. 투표 유형별 차별 적용

Poll 모델에 `required_verification` 필드 추가:

| 투표 유형 | 인증 수준 | 적용 방어 |
|-----------|-----------|-----------|
| 재미/가벼운 투표 | Tier 1 | 로그인 + Rate Limit + Turnstile |
| 일반 여론조사 | Tier 2 | + Fingerprint + SMS |
| 공식/중요 투표 | Tier 3 | + 본인인증(DI) + VPN 탐지 |

---

## 5. Fraud Score 시스템 설계

```
fraud_score 계산 (0~100):
  같은 IP에서 이전 투표:   +20
  VPN/프록시 감지:         +25
  새 계정(가입 1시간 이내): +15
  핑거프린트 중복:          +30
  Turnstile 점수 낮음:     +15
  비정상 행동 패턴:         +20
  이메일 패턴 의심:         +10

임계값:
  0~30:  정상 → 투표 허용
  31~60: 주의 → 허용 + 모니터링
  61~80: 경고 → 추가 인증 요구 (SMS/CAPTCHA)
  81~100: 차단 → 투표 거부 + 관리자 알림
```

---

## 6. DB 스키마 변경 (필요 시)

```python
# Vote 모델 확장
voter_ip: str | None
voter_fingerprint: str | None
fraud_score: int = 0
verification_level: str  # "NONE", "SMS", "IDENTITY"

# User 모델 확장
phone_hash: str | None (unique)       # 전화번호 SHA256
di_hash: str | None (unique)          # 본인인증 DI SHA256
phone_verified_at: datetime | None
identity_verified_at: datetime | None

# Poll 모델 확장
required_verification: str  # "NONE", "LOGIN", "SMS", "IDENTITY"

# 새 테이블: vote_audit_logs
id, vote_id, ip_address, fingerprint, user_agent,
fraud_score, fraud_signals(JSON), created_at
```

---

## 7. 구현 로드맵

| Phase | 기간 | 내용 |
|-------|------|------|
| **Phase 1** | 1~2일 | Tier 1 전체 (로그인 필수, Rate Limit, IP 로깅) |
| **Phase 2** | 1주차 | Cloudflare Turnstile + IP 중복 감지 |
| **Phase 3** | 2~3주차 | Fingerprint Pro + SMS 인증 + Fraud Score 기본 |
| **Phase 4** | 1~2개월 | BaroCert 본인인증 + VPN 탐지 + 통계 이상 탐지 |

---

## 8. 참고 자료

- [BaroCert 인증 API](https://www.barocert.com/) - 카카오/네이버/토스 통합
- [NICE 본인인증](https://www.niceapi.co.kr/)
- [CI/DI 차이점](https://www.ihee.com/614)
- [Aligo SMS API](https://smartsms.aligo.in/smsapi.html)
- [Fingerprint Pro](https://fingerprint.com/pricing/)
- [IPQualityScore](https://www.ipqualityscore.com/plans)
- [Cloudflare Turnstile](https://www.cloudflare.com/application-services/products/turnstile/)
- [에스토니아 i-Voting](https://en.wikipedia.org/wiki/Electronic_voting_in_Estonia)
- [KISA 본인확인 지원포털](https://identity.kisa.or.kr/web/main/contents/M010-02)
