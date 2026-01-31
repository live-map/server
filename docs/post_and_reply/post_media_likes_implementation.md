# Post Media & Likes 구현 문서

---

## 1. Overall Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              전체 요청 흐름                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

  Client Request
       │
       ▼
  ┌─────────────────┐
  │   Controller    │  ← HTTP 요청 수신, JWT 인증, 입력 검증
  │  (controller.py)│
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │    Service      │  ← 비즈니스 로직, 트랜잭션 commit()
  │   (service.py)  │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │   Repository    │  ← DB CRUD, flush()만 수행
  │ (repository.py) │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐
  │   PostgreSQL    │
  └─────────────────┘
```

### 핵심 설계 원칙

1. **Post Controller 통합**: 미디어와 좋아요는 별도 컨트롤러 없이 Post Controller에서 통합 처리
2. **트랜잭션 분리**: Repository는 `flush()`만, Service에서 `commit()`
3. **미디어는 URL만 저장**: 파일은 클라이언트→S3 직접 업로드, 서버는 메타데이터만 저장
4. **좋아요 비정규화**: `Post.like_count` 필드로 성능 최적화

---

## 2. Error Prevention (에러 방지 설계)

이 섹션에서는 구현 과정에서 발생할 수 있는 잠재적 오류들과 이를 방지하기 위한 설계를 설명합니다.

### 2.1 단일 MediaType Enum 사용

**문제**: 동일한 Enum이 여러 파일에 정의되면 타입 불일치 발생 가능

```
# 수정 전 (문제)
app/models/post_media.py     → class MediaType(str, Enum): ...
app/api/v1/post/dto/schemas.py → class MediaType(str, Enum): ...  # 중복!
```

**해결**: `schemas.py`에서 모델의 `MediaType`을 import하여 단일 소스 유지

```python
# schemas.py
from app.models.post_media import MediaType  # 단일 소스 import
```

**효과**: Enum 값 불일치로 인한 런타임 에러 방지

---

### 2.2 단일 트랜잭션으로 게시글 + 미디어 생성

**문제**: 게시글과 미디어가 별도 트랜잭션으로 처리되면 데이터 불일치 발생

```
# 수정 전 (문제)
post = await postService.create_post(...)  # commit ①
media = await mediaService.add_media(...)  # commit ②  ← 실패 시 post만 존재
```

**해결**: `create_post_without_commit()` 메서드로 트랜잭션 유지

```python
# 수정 후 (해결)
post = await postService.create_post_without_commit(...)  # flush만
media = await mediaService.add_multiple_media_without_commit(...)  # flush만
await postService.session.commit()  # 모든 작업 한 번에 commit
```

**효과**: 미디어 저장 실패 시 게시글도 롤백되어 고아 데이터 방지

---

### 2.3 도메인 예외와 HTTP 예외 분리

**문제**: Service 레이어에서 `HTTPException`을 직접 던지면 계층 분리 원칙 위반

```python
# 수정 전 (문제) - service.py
if post.user_id != user_id:
    raise HTTPException(status_code=403, ...)  # HTTP 계층이 Service에 침투
    return None  # 죽은 코드!
```

**해결**: 도메인 예외 정의 후 Controller에서 HTTP 예외로 변환

```python
# service.py - 도메인 예외 정의
class PostNotFoundError(Exception): pass
class PostPermissionError(Exception): pass

# service.py - 도메인 예외 발생
if post.user_id != user_id:
    raise PostPermissionError(f"User {user_id} is not the owner")

# controller.py - HTTP 예외로 변환
try:
    post = await service.update_post(...)
except PostNotFoundError:
    raise HTTPException(status_code=404, detail="Post not found")
except PostPermissionError:
    raise HTTPException(status_code=403, detail="You are not the owner")
```

**효과**:
- 계층 분리 원칙 준수
- 명확한 에러 메시지 (404 vs 403 구분)
- 죽은 코드 제거

---

### 2.4 Race Condition 방지 (좋아요)

**문제**: 컨트롤러에서 게시글 확인 후 서비스에서 좋아요 생성 사이에 게시글이 삭제될 수 있음

```
# 수정 전 (문제)
Controller: post = await postService.get_post(post_id)  # 존재함
Controller: if post is None: raise 404
            │
            │  ← 다른 요청이 게시글 삭제
            ▼
Service:    like = await likeService.like_post(post_id)  # 삭제된 게시글에 좋아요!
```

**해결**: 서비스 레이어에서 좋아요 생성 직전 게시글 상태 확인

```python
# like/service.py
async def like_post(self, post_id, user_id):
    # 서비스 내에서 게시글 상태 확인 (같은 트랜잭션)
    post_exists = await self.like_repo.check_post_exists_and_active(post_id)
    if not post_exists:
        raise PostNotFoundForLikeError(...)

    # increment_like_count도 is_deleted=False 조건 포함
    updated = await self.like_repo.increment_like_count(post_id)
    if not updated:
        await self.session.rollback()
        raise PostNotFoundForLikeError(...)
```

```python
# like/repository.py
async def increment_like_count(self, post_id) -> bool:
    stmt = (
        update(Post)
        .where(Post.id == post_id, Post.is_deleted == False)  # 삭제 안된 것만
        .values(like_count=Post.like_count + 1)
    )
    result = await self.session.execute(stmt)
    return result.rowcount > 0  # 업데이트 성공 여부 반환
```

**효과**: 삭제된 게시글에 좋아요가 추가되는 것 방지

---

### 2.5 like_count 동기화 문제 방지

**문제**: `like_count`가 이미 0인데 unlike 시도하면 desync 발생

```
# 수정 전 (문제)
like_count = 0인 상태에서:
1. decrement_like_count() → 실패 (0보다 작아질 수 없음)
2. delete() → 성공 (PostLike 삭제됨)
→ 실제 좋아요 수와 like_count 불일치!
```

**해결**: decrement 실패해도 PostLike는 삭제하고 로그 남김

```python
# like/service.py
async def unlike_post(self, post_id, user_id):
    updated = await self.like_repo.decrement_like_count(post_id)

    if updated:
        await self.like_repo.delete(post_id, user_id)
    else:
        # desync 감지 - 삭제는 수행하고 경고 로그
        logger.warning(f"like_count desync detected for post {post_id}")
        await self.like_repo.delete(post_id, user_id)
```

**효과**:
- desync 상황 감지 및 로깅
- PostLike 레코드는 항상 정리됨
- 운영자가 desync 로그를 통해 문제 인지 가능

---

### 2.6 URL 검증으로 보안 강화

**문제**: 임의의 URL을 저장할 수 있으면 XSS, 피싱 등 보안 위협

```python
# 수정 전 (문제)
url: str = Field(..., max_length=1000)  # 아무 URL이나 허용
```

**해결**: S3/CloudFront URL만 허용하는 검증 추가

```python
# schemas.py
ALLOWED_MEDIA_URL_PATTERN = re.compile(
    r"^https://([\w-]+\.s3\.[\w-]+\.amazonaws\.com|[\w-]+\.cloudfront\.net|localhost:\d+)/.*$",
    re.IGNORECASE,
)

class PostMediaCreate(BaseModel):
    url: str = Field(..., max_length=1000)

    @field_validator("url", "thumbnail_url")
    @classmethod
    def validate_url(cls, v):
        if v and not ALLOWED_MEDIA_URL_PATTERN.match(v):
            raise ValueError("URL must be from allowed domains")
        return v
```

**효과**:
- 외부 악성 URL 저장 방지
- S3 버킷 외부 리소스 참조 차단

---

### 2.7 미디어 개수 제한

**문제**: 무제한 미디어 첨부 시 DB 부하 및 남용 가능

```python
# 수정 전 (문제)
media: list[PostMediaCreate] | None = Field(None)  # 무제한
```

**해결**: 최대 10개로 제한

```python
# schemas.py
MAX_MEDIA_PER_POST = 10

class PostCreate(BaseModel):
    media: list[PostMediaCreate] | None = Field(
        None,
        max_length=MAX_MEDIA_PER_POST,  # Pydantic 검증
        description=f"Optional media attachments (max {MAX_MEDIA_PER_POST})",
    )
```

**효과**: API 레벨에서 미디어 개수 제한으로 남용 방지

---

### 2.8 복합 인덱스로 쿼리 성능 최적화

**문제**: `ORDER BY order` 쿼리 시 인덱스 없으면 전체 스캔

```sql
-- 인덱스 없이
SELECT * FROM post_media WHERE post_id = ? ORDER BY order;  -- Full scan
```

**해결**: `(post_id, order)` 복합 인덱스 추가

```python
# models/post_media.py
__table_args__ = (
    Index("ix_post_media_post_id_order", "post_id", "order"),
)
```

**효과**: 미디어 조회 쿼리 성능 향상 (특히 미디어가 많은 게시글)

---

## 3. Post Controller 코드 설명

**파일**: `app/api/v1/post/controller.py`

### 3.1 의존성 주입 설정 (Lines 51-74)

```python
# Lines 51-56: PostService 의존성 생성 함수
async def get_post_service(
    session: Annotated[AsyncSession, Depends(get_db)],  # DB 세션 주입
) -> PostService:
    """PostService 의존성 주입."""
    return PostService(session)  # 세션을 넘겨 서비스 인스턴스 생성

# Lines 58-63: PostMediaService 의존성 생성 함수
async def get_media_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PostMediaService:
    """PostMediaService 의존성 주입."""
    return PostMediaService(session)

# Lines 65-70: PostLikeService 의존성 생성 함수
async def get_like_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PostLikeService:
    """PostLikeService 의존성 주입."""
    return PostLikeService(session)

# Lines 72-74: 타입 별칭 정의 (코드 간결화)
postServiceDep = Annotated[PostService, Depends(get_post_service)]
mediaServiceDep = Annotated[PostMediaService, Depends(get_media_service)]
likeServiceDep = Annotated[PostLikeService, Depends(get_like_service)]
```

**동작 원리**:
- FastAPI의 `Depends()`가 요청마다 DB 세션을 생성
- 세션을 각 Service에 주입하여 인스턴스 생성
- 모든 Service가 동일 세션을 공유 → 하나의 트랜잭션으로 처리 가능

---

### 3.2 게시글 생성 + 미디어 첨부 (단일 트랜잭션)

```python
@router.post("", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    data: PostCreate,                    # Pydantic 스키마로 입력 검증 (미디어 최대 10개)
    current_user: CurrentUser,           # JWT에서 추출한 사용자 정보
    postService: Annotated[PostService, Depends(get_post_service)],
    mediaService: mediaServiceDep,
) -> PostResponse:

    # 게시글 생성 (commit 없이 트랜잭션 유지)
    post = await postService.create_post_without_commit(
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    # 미디어 첨부 처리 (같은 트랜잭션 내에서)
    media_responses = []
    if data.media:
        created_media = await mediaService.add_multiple_media_without_commit(
            post_id=post.id,
            media_data_list=[...],
        )
        media_responses = [PostMediaResponse(...) for m in created_media]

    # 모든 작업이 성공하면 한 번에 commit
    await postService.session.commit()

    return PostResponse(...)
```

**핵심 변경**:
- `create_post()` → `create_post_without_commit()` 사용
- `add_multiple_media_to_post()` → `add_multiple_media_without_commit()` 사용
- 마지막에 `session.commit()` 한 번만 호출
- **효과**: 미디어 저장 실패 시 게시글도 롤백

---

### 3.3 게시글 수정 (예외 처리 분리)

```python
@router.patch("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: uuid.UUID,
    data: PostUpdate,
    current_user: CurrentUser,
    service: postServiceDep,
) -> PostResponse:
    try:
        post = await service.update_post(
            post_id=post_id,
            user_id=current_user.user_id,
            title=data.title,
            content=data.content,
        )
    except PostNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",  # 명확한 에러 메시지
        )
    except PostPermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not the owner of this post",  # 권한 오류 분리
        )

    return PostResponse(...)
```

**핵심 변경**:
- 도메인 예외 (`PostNotFoundError`, `PostPermissionError`)를 catch
- 각각 적절한 HTTP 상태 코드로 변환 (404 vs 403)
- 모호한 "Post not found or no permission" 메시지 제거

---

### 3.4 좋아요 추가 (Race Condition 방지)

```python
@router.post("/{post_id}/like", response_model=LikeResponse)
async def like_post(
    post_id: uuid.UUID,
    current_user: CurrentUser,
    likeService: likeServiceDep,
) -> LikeResponse:
    """
    Note: 게시글 존재 확인은 서비스 레이어에서 수행됩니다.
    이는 컨트롤러 확인과 서비스 실행 사이의 race condition을 방지합니다.
    """
    try:
        result = await likeService.like_post(post_id, current_user.user_id)
    except PostNotFoundForLikeError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or has been deleted",
        )

    return LikeResponse(...)
```

**핵심 변경**:
- 컨트롤러에서 `postService.get_post()` 제거
- 서비스 내부에서 게시글 상태 확인 (같은 트랜잭션)
- Race condition 방지

---

## 4. PostMediaService 코드 설명

**파일**: `app/api/v1/post/media/service.py`

### 4.1 트랜잭션 분리된 메서드

```python
async def add_media_to_post(self, ...) -> PostMedia:
    """미디어 추가 (commit 포함) - 단독 사용 시"""
    created = await self.add_media_to_post_without_commit(...)
    await self.session.commit()
    return created

async def add_multiple_media_without_commit(self, ...) -> list[PostMedia]:
    """미디어 일괄 추가 (commit 없음) - 게시글과 함께 생성 시"""
    media_list = []
    for idx, data in enumerate(media_data_list):
        media = PostMedia(
            post_id=post_id,
            media_type=data["media_type"],
            url=data["url"],
            ...
        )
        media_list.append(media)

    created_list = await self.media_repo.create_many(media_list)
    # commit 없음 - 호출자가 담당
    return created_list
```

**설계 의도**:
- `*_without_commit()` 메서드는 트랜잭션 제어를 호출자에게 위임
- 게시글 + 미디어 원자적 생성 가능

---

## 5. PostLikeService 코드 설명

**파일**: `app/api/v1/post/like/service.py`

### 5.1 Race Condition 방지 좋아요

```python
async def like_post(self, post_id: uuid.UUID, user_id: str) -> LikeResult:
    # 1. 게시글 존재 및 활성 상태 확인 (같은 트랜잭션)
    post_exists = await self.like_repo.check_post_exists_and_active(post_id)
    if not post_exists:
        raise PostNotFoundForLikeError(f"Post {post_id} not found or deleted")

    # 2. 중복 좋아요 확인
    already_liked = await self.like_repo.exists(post_id, user_id)
    if already_liked:
        return LikeResult(success=False, is_liked=True, ...)

    # 3. 좋아요 생성
    like = PostLike(post_id=post_id, user_id=user_id)
    await self.like_repo.create(like)

    # 4. like_count 증가 (실패 시 롤백)
    updated = await self.like_repo.increment_like_count(post_id)
    if not updated:
        await self.session.rollback()
        raise PostNotFoundForLikeError(...)

    await self.session.commit()
    return LikeResult(success=True, is_liked=True, ...)
```

**Race Condition 방지 포인트**:
1. `check_post_exists_and_active()`: 좋아요 전 게시글 상태 확인
2. `increment_like_count()`: `is_deleted=False` 조건 포함
3. 실패 시 `rollback()`으로 일관성 유지

### 5.2 like_count Desync 처리

```python
async def unlike_post(self, post_id: uuid.UUID, user_id: str) -> LikeResult:
    is_liked = await self.like_repo.exists(post_id, user_id)
    if not is_liked:
        return LikeResult(success=False, is_liked=False, ...)

    # like_count 감소 먼저 시도
    updated = await self.like_repo.decrement_like_count(post_id)

    if updated:
        await self.like_repo.delete(post_id, user_id)
    else:
        # desync 감지: like_count=0인데 좋아요 존재
        logger.warning(f"like_count desync detected for post {post_id}")
        await self.like_repo.delete(post_id, user_id)  # 삭제는 수행

    await self.session.commit()
    return LikeResult(success=True, is_liked=False, ...)
```

**Desync 처리 전략**:
- `decrement_like_count()` 실패해도 PostLike 삭제는 수행
- 경고 로그로 운영자에게 desync 알림
- 데이터 정합성 점진적 복구 가능

---

## 6. PostLikeRepository 코드 설명

**파일**: `app/api/v1/post/like/repository.py`

### 6.1 게시글 상태 확인

```python
async def check_post_exists_and_active(self, post_id: uuid.UUID) -> bool:
    """게시글 존재 및 활성 상태 확인 (is_deleted=False)."""
    stmt = select(Post.id).where(
        Post.id == post_id,
        Post.is_deleted == False,
    )
    result = await self.session.execute(stmt)
    return result.scalar_one_or_none() is not None
```

### 6.2 원자적 like_count 증가 (삭제 확인 포함)

```python
async def increment_like_count(self, post_id: uuid.UUID) -> bool:
    """is_deleted=False인 게시글에만 like_count 증가."""
    stmt = (
        update(Post)
        .where(Post.id == post_id, Post.is_deleted == False)  # 삭제 안된 것만
        .values(like_count=Post.like_count + 1)
    )
    result = await self.session.execute(stmt)
    return result.rowcount > 0  # 업데이트 성공 여부
```

### 6.3 원자적 like_count 감소 (음수 방지)

```python
async def decrement_like_count(self, post_id: uuid.UUID) -> bool:
    """like_count > 0일 때만 감소."""
    stmt = (
        update(Post)
        .where(Post.id == post_id, Post.like_count > 0)  # 음수 방지
        .values(like_count=Post.like_count - 1)
    )
    result = await self.session.execute(stmt)
    return result.rowcount > 0  # 실패 시 False (이미 0이거나 없음)
```

---

## 7. Schemas 코드 설명

**파일**: `app/api/v1/post/dto/schemas.py`

### 7.1 URL 검증

```python
ALLOWED_MEDIA_URL_PATTERN = re.compile(
    r"^https://([\w-]+\.s3\.[\w-]+\.amazonaws\.com|[\w-]+\.cloudfront\.net|localhost:\d+)/.*$",
    re.IGNORECASE,
)

class PostMediaCreate(BaseModel):
    url: str = Field(..., max_length=1000)

    @field_validator("url", "thumbnail_url")
    @classmethod
    def validate_url(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not ALLOWED_MEDIA_URL_PATTERN.match(v):
            raise ValueError("URL must be from allowed domains")
        return v
```

**허용 도메인**:
- `*.s3.*.amazonaws.com` (S3 직접)
- `*.cloudfront.net` (CloudFront CDN)
- `localhost:*` (개발 환경)

### 7.2 미디어 개수 제한

```python
MAX_MEDIA_PER_POST = 10

class PostCreate(BaseModel):
    media: list[PostMediaCreate] | None = Field(
        None,
        max_length=MAX_MEDIA_PER_POST,
        description=f"Optional media attachments (max {MAX_MEDIA_PER_POST})",
    )
```

### 7.3 파일 크기/해상도 제한

```python
class PostMediaCreate(BaseModel):
    file_size: int | None = Field(None, ge=0, le=104857600)  # max 100MB
    width: int | None = Field(None, ge=0, le=7680)  # max 8K
    height: int | None = Field(None, ge=0, le=4320)  # max 8K
    duration: int | None = Field(None, ge=0, le=60)  # max 60초
```

---

## 8. 데이터베이스 스키마

### post_media 테이블

```sql
CREATE TABLE post_media (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    media_type media_type_enum NOT NULL,
    url VARCHAR(1000) NOT NULL,
    thumbnail_url VARCHAR(1000),
    original_filename VARCHAR(255),
    file_size INTEGER,
    duration INTEGER,
    width INTEGER,
    height INTEGER,
    "order" INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 복합 인덱스 (성능 최적화)
CREATE INDEX ix_post_media_post_id_order ON post_media(post_id, "order");
```

### post_likes 테이블

```sql
CREATE TABLE post_likes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    user_id VARCHAR(25) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_post_like_post_user UNIQUE (post_id, user_id)
);

CREATE INDEX ix_post_likes_post_id ON post_likes(post_id);
CREATE INDEX ix_post_likes_user_id ON post_likes(user_id);
```

---

## 9. 에러 방지 요약 표

| # | 문제 | 해결책 | 효과 |
|---|------|--------|------|
| 1 | MediaType 중복 정의 | 단일 소스 import | 타입 불일치 방지 |
| 2 | 분리된 트랜잭션 | `*_without_commit()` 메서드 | 원자성 보장 |
| 3 | HTTPException in Service | 도메인 예외 분리 | 계층 분리, 명확한 에러 |
| 4 | 좋아요 Race Condition | 서비스 내 상태 확인 | 삭제된 게시글 좋아요 방지 |
| 5 | like_count 음수 | `like_count > 0` 조건 | 음수 값 방지 |
| 6 | like_count desync | 로그 + 삭제 수행 | 점진적 복구 가능 |
| 7 | 악성 URL 저장 | URL 패턴 검증 | 보안 위협 차단 |
| 8 | 무제한 미디어 | `max_length=10` | 남용 방지 |
| 9 | ORDER BY 느림 | 복합 인덱스 | 쿼리 성능 향상 |

---

*최종 수정: 2026-01-30*
