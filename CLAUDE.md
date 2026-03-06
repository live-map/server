# Claude 작업 규칙

## 필수 사항

### 1. 테스트
- 코드 작성 후 반드시 직접 테스트
- 서버 실행하여 API 엔드포인트 확인
- 에러 발생 시 즉시 수정

### 2. 베스트 프랙티스 조사
- FastAPI 공식 문서 및 최신 패턴 지속 확인
- 코드 작성 전 관련 베스트 프랙티스 조사
- 필요시 에이전트 활용하여 병렬 조사

### 3. Git 워크플로우
- feature 브랜치에서 작업
- 완료 후 dev로 머지
- 커밋 시 Obsidian에 기록

### 4. Obsidian 기록
- 커밋마다 작업 내용 기록
- Why/What/How/Result 형식
- `/Users/iyeonsang/Desktop/obsidian/work/projects/livemap/commits/`

## FastAPI 베스트 프랙티스 (조사 결과 업데이트)

### 프로젝트 구조 (Grapoll - 여론조사 플랫폼)
```
app/
├── api/v1/
│   ├── poll/              # 여론조사 모듈 (Controller→Service→Repository)
│   │   ├── controller.py  # 12개 엔드포인트
│   │   ├── service.py     # PollService
│   │   ├── repository.py  # PollRepository
│   │   ├── dto/schemas.py # Pydantic 스키마 (camelCase alias)
│   │   ├── vote/          # 투표 서브모듈
│   │   └── comment/       # 댓글 서브모듈
│   ├── post/              # 커뮤니티 게시글 (동일 패턴)
│   ├── comment/           # 커뮤니티 댓글
│   ├── media/             # 미디어 업로드
│   └── interpreter/       # JWT 인증 가드
├── core/                  # 설정, 보안, 예외
├── db/                    # 데이터베이스
├── models/                # SQLAlchemy 모델 (Poll, Vote, PollComment, Post, Comment, User)
├── services/              # 공통 서비스 (S3 등)
├── main.py
fly.toml                   # Fly.io 배포 설정 (Tokyo nrt)
```

### 의존성 주입
- `Depends()`로 DB 세션, 인증 등 주입
- 재사용 가능한 의존성 함수 작성

### 비동기
- async/await 일관성 있게 사용
- DB 작업은 asyncpg + SQLAlchemy async

### 에러 처리
- HTTPException으로 일관된 에러 응답
- 커스텀 예외 핸들러 등록

### 검증
- Pydantic 스키마로 입력 검증
- Field()로 상세 검증 규칙

### ML 모델 의존성 주입
- lifespan 이벤트로 모델 로딩
- app.state에 모델 저장
- CPU-bound 작업은 run_in_threadpool 사용

```python
from contextlib import asynccontextmanager
from fastapi.concurrency import run_in_threadpool

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 시작 시 모델 로딩
    app.state.nlp = spacy.load("en_core_web_lg")
    yield
    # 종료 시 정리

# CPU-bound 작업
result = await run_in_threadpool(cpu_bound_function, arg1, arg2)
```

### 서비스 레이어
- 비즈니스 로직은 services/ 분리
- 라우터는 요청/응답만 담당
- 의존성으로 서비스 주입

---
*이 파일은 Claude가 자동 업데이트합니다*
