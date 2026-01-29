# Service Layer Documentation

Post, Media, Like 서비스 레이어에 대한 상세 문서입니다.

---

## 목차

1. [PostService](#postservice)
2. [PostMediaService](#postmediaservice)
3. [PostLikeService](#postlikeservice)
4. [Repository Layer](#repository-layer)

---

## PostService

**파일**: `app/api/v1/post/service.py`

게시글 CRUD 비즈니스 로직을 처리합니다.

### 메서드

#### create_post

```python
async def create_post(
    user_id: str,
    title: str,
    content: str,
) -> Post
```

새 게시글을 생성합니다.

**Parameters**:
- `user_id`: 작성자 ID
- `title`: 게시글 제목 (1-200자)
- `content`: 게시글 내용

**Returns**: 생성된 `Post` 객체

---

#### get_post

```python
async def get_post(post_id: uuid.UUID) -> Post | None
```

게시글 단건 조회 (소프트 삭제된 게시글 제외).

---

#### get_post_with_comments

```python
async def get_post_with_comments(post_id: uuid.UUID) -> Post | None
```

게시글과 댓글, 미디어를 함께 조회합니다 (Eager loading).

---

#### list_posts

```python
async def list_posts(
    limit: int = 20,
    offset: int = 0,
    user_id: str | None = None,
) -> Sequence[Post]
```

게시글 목록을 페이지네이션으로 조회합니다.
User, Comments, Media를 Eager loading 합니다.

---

#### update_post

```python
async def update_post(
    post_id: uuid.UUID,
    user_id: str,
    title: str | None = None,
    content: str | None = None,
) -> Post | None
```

게시글을 수정합니다.

**권한 확인**: 작성자만 수정 가능
- 작성자가 아닌 경우 `HTTPException(403)` 발생

---

#### delete_post

```python
async def delete_post(post_id: uuid.UUID, user_id: str) -> bool
```

게시글을 소프트 삭제합니다 (`is_deleted = True`).

**권한 확인**: 작성자만 삭제 가능

---

## PostMediaService

**파일**: `app/api/v1/post/media/service.py`

미디어 첨부 관련 비즈니스 로직을 처리합니다.

### 메서드

#### add_media_to_post

```python
async def add_media_to_post(
    post_id: uuid.UUID,
    media_type: MediaType,
    url: str,
    thumbnail_url: str | None = None,
    original_filename: str | None = None,
    file_size: int | None = None,
    duration: int | None = None,
    width: int | None = None,
    height: int | None = None,
    order: int = 0,
) -> PostMedia
```

게시글에 미디어를 추가합니다.

**사용 시나리오**:
1. 클라이언트가 S3에 파일 업로드
2. 업로드 완료 후 이 메서드 호출하여 메타데이터 저장

**Parameters**:
- `post_id`: 게시글 UUID
- `media_type`: `MediaType.IMAGE` 또는 `MediaType.VIDEO`
- `url`: S3/CloudFront URL
- `thumbnail_url`: 비디오 썸네일 URL (선택)
- `original_filename`: 원본 파일명 (선택)
- `file_size`: 파일 크기 bytes (선택)
- `duration`: 비디오 길이 초 (선택, 최대 60)
- `width`: 너비 pixels (선택)
- `height`: 높이 pixels (선택)
- `order`: 표시 순서 (기본 0)

---

#### add_multiple_media_to_post

```python
async def add_multiple_media_to_post(
    post_id: uuid.UUID,
    media_data_list: list[dict],
) -> list[PostMedia]
```

여러 미디어를 일괄 추가합니다.

**media_data_list 형식**:
```python
[
    {
        "media_type": MediaType.IMAGE,
        "url": "https://...",
        "thumbnail_url": None,
        "original_filename": "photo.jpg",
        "file_size": 123456,
        "duration": None,
        "width": 1920,
        "height": 1080,
        "order": 0,
    },
    # ...
]
```

---

#### get_post_media

```python
async def get_post_media(post_id: uuid.UUID) -> Sequence[PostMedia]
```

게시글의 모든 미디어를 `order` 순으로 조회합니다.

---

#### delete_media

```python
async def delete_media(media_id: uuid.UUID) -> bool
```

미디어 레코드를 삭제합니다.

**주의**: S3의 실제 파일은 별도로 삭제해야 합니다.

---

#### delete_all_post_media

```python
async def delete_all_post_media(post_id: uuid.UUID) -> int
```

게시글의 모든 미디어를 삭제합니다.

**Returns**: 삭제된 미디어 수

---

#### reorder_media

```python
async def reorder_media(
    post_id: uuid.UUID,
    media_order: list[uuid.UUID],
) -> list[PostMedia]
```

미디어 순서를 재정렬합니다.

**Parameters**:
- `media_order`: 새 순서대로 정렬된 미디어 UUID 목록

---

## PostLikeService

**파일**: `app/api/v1/post/like/service.py`

좋아요 관련 비즈니스 로직을 처리합니다.

### LikeResult

좋아요 작업 결과를 담는 데이터 클래스:

```python
@dataclass
class LikeResult:
    success: bool      # 작업 성공 여부
    is_liked: bool     # 현재 좋아요 상태
    like_count: int    # 현재 좋아요 수
    message: str       # 결과 메시지
```

### 메서드

#### like_post

```python
async def like_post(post_id: uuid.UUID, user_id: str) -> LikeResult
```

게시글에 좋아요를 추가합니다.

**동작**:
1. 이미 좋아요한 경우 → `success=False` 반환
2. 좋아요 레코드 생성
3. `Post.like_count += 1`
4. 결과 반환

---

#### unlike_post

```python
async def unlike_post(post_id: uuid.UUID, user_id: str) -> LikeResult
```

게시글 좋아요를 취소합니다.

**동작**:
1. 좋아요하지 않은 경우 → `success=False` 반환
2. 좋아요 레코드 삭제
3. `Post.like_count -= 1`
4. 결과 반환

---

#### toggle_like

```python
async def toggle_like(post_id: uuid.UUID, user_id: str) -> LikeResult
```

좋아요 상태를 토글합니다.
- 좋아요 상태 → 취소
- 미좋아요 상태 → 좋아요

---

#### is_liked_by_user

```python
async def is_liked_by_user(post_id: uuid.UUID, user_id: str) -> bool
```

사용자의 좋아요 여부를 확인합니다.

---

#### get_like_status_for_posts

```python
async def get_like_status_for_posts(
    post_ids: list[uuid.UUID],
    user_id: str,
) -> dict[uuid.UUID, bool]
```

여러 게시글에 대한 좋아요 상태를 일괄 조회합니다.

**사용 시나리오**: 게시글 목록 API에서 N+1 쿼리 방지

**Example**:
```python
status = await like_service.get_like_status_for_posts(
    post_ids=[uuid1, uuid2, uuid3],
    user_id="user123"
)
# {uuid1: True, uuid2: False, uuid3: True}
```

---

#### get_post_likers

```python
async def get_post_likers(
    post_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[PostLike]
```

게시글을 좋아요한 사용자 목록을 조회합니다.
User 정보를 Eager loading 합니다.

---

#### get_user_liked_posts

```python
async def get_user_liked_posts(
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> Sequence[PostLike]
```

사용자가 좋아요한 게시글 목록을 조회합니다.

---

## Repository Layer

### PostRepository

**파일**: `app/api/v1/post/repository.py`

| 메서드 | 설명 |
|--------|------|
| `create(post)` | 게시글 생성 |
| `get_by_id(post_id)` | ID로 조회 |
| `get_by_id_with_comments(post_id)` | 댓글, 미디어 포함 조회 |
| `get_all(limit, offset, user_id?)` | 목록 조회 |
| `update(post)` | 게시글 수정 |
| `soft_delete(post_id)` | 소프트 삭제 |
| `hard_delete(post_id)` | 완전 삭제 (Admin) |
| `count(user_id?)` | 게시글 수 |

### PostMediaRepository

**파일**: `app/api/v1/post/media/repository.py`

| 메서드 | 설명 |
|--------|------|
| `create(media)` | 미디어 생성 |
| `create_many(media_list)` | 일괄 생성 |
| `get_by_id(media_id)` | ID로 조회 |
| `get_by_post_id(post_id)` | 게시글의 미디어 조회 |
| `delete(media_id)` | 미디어 삭제 |
| `delete_by_post_id(post_id)` | 게시글의 모든 미디어 삭제 |
| `update_order(media_id, new_order)` | 순서 변경 |
| `count_by_post_id(post_id)` | 미디어 수 |

### PostLikeRepository

**파일**: `app/api/v1/post/like/repository.py`

| 메서드 | 설명 |
|--------|------|
| `create(like)` | 좋아요 생성 |
| `delete(post_id, user_id)` | 좋아요 삭제 |
| `exists(post_id, user_id)` | 좋아요 존재 확인 |
| `get_by_post_id(post_id, limit, offset)` | 게시글의 좋아요 목록 |
| `get_user_liked_posts(user_id, limit, offset)` | 사용자의 좋아요 목록 |
| `count_by_post_id(post_id)` | 좋아요 수 |
| `increment_like_count(post_id)` | like_count +1 |
| `decrement_like_count(post_id)` | like_count -1 |
| `get_like_status_for_posts(post_ids, user_id)` | 일괄 좋아요 상태 조회 |

---

*최종 수정: 2026-01-28*
