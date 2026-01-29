# Post & Reply System Documentation

게시글, 댓글, 미디어, 좋아요 기능에 대한 문서입니다.

---

## 목차

1. [개요](#개요)
2. [아키텍처](#아키텍처)
3. [데이터 모델](#데이터-모델)
4. [API 엔드포인트](#api-엔드포인트)
5. [서비스 레이어](#서비스-레이어)
6. [미디어 업로드 (S3)](#미디어-업로드-s3)
7. [좋아요 시스템](#좋아요-시스템)

---

## 개요

Post & Reply 시스템은 다음 기능을 제공합니다:

- **게시글 (Post)**: CRUD 작업, 소프트 삭제 지원
- **댓글 (Comment)**: 무한 대댓글 지원 (self-join)
- **미디어 (PostMedia)**: 이미지/비디오 첨부 (AWS S3)
- **좋아요 (PostLike)**: 사용자별 좋아요 추적

---

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Post & Reply Architecture                             │
└─────────────────────────────────────────────────────────────────────────────────┘

  Request Flow:
  ┌─────────┐    ┌────────────┐    ┌──────────┐    ┌────────────┐    ┌──────────┐
  │ Client  │───▶│ Controller │───▶│ Service  │───▶│ Repository │───▶│ Database │
  └─────────┘    └────────────┘    └──────────┘    └────────────┘    └──────────┘
                       │
                       ▼
               ┌──────────────┐
               │  JWT Guard   │
               │ (Middleware) │
               └──────────────┘

  Directory Structure:
  app/api/v1/post/
  ├── controller.py          # API 라우트 핸들러
  ├── service.py             # Post 비즈니스 로직
  ├── repository.py          # Post 데이터 접근
  ├── dto/
  │   └── schemas.py         # Pydantic 스키마
  ├── media/
  │   ├── __init__.py
  │   ├── repository.py      # PostMedia 데이터 접근
  │   └── service.py         # PostMedia 비즈니스 로직
  └── like/
      ├── __init__.py
      ├── repository.py      # PostLike 데이터 접근
      └── service.py         # PostLike 비즈니스 로직
```

---

## 데이터 모델

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   Data Model                                     │
└─────────────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │    User     │
                              │             │
                              │  id (CUID)  │
                              │  name       │
                              │  email      │
                              └──────┬──────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
             ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
             │    Post     │  │  PostLike   │  │   Comment   │
             │             │  │             │  │             │
             │  id (UUID)  │◀─│  post_id    │  │  post_id    │
             │  user_id    │  │  user_id    │  │  user_id    │
             │  title      │  │  created_at │  │  parent_id  │──┐
             │  content    │  └─────────────┘  │  content    │  │ (self-join)
             │  like_count │                   │  depth      │◀─┘
             └──────┬──────┘                   └─────────────┘
                    │
                    ▼
             ┌─────────────┐
             │  PostMedia  │
             │             │
             │  id (UUID)  │
             │  post_id    │  (FK to Post)
             │  media_type │  (IMAGE/VIDEO)
             │  url        │  (S3/CloudFront URL)
             │  thumbnail  │  (비디오 썸네일)
             │  duration   │  (비디오 길이, 최대 60초)
             └─────────────┘
```

### 테이블 상세

#### posts

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid_generate_v4() | PK |
| user_id | VARCHAR(25) | NO | - | FK to users |
| title | VARCHAR(200) | NO | - | 게시글 제목 |
| content | TEXT | NO | - | 게시글 내용 |
| like_count | INTEGER | NO | 0 | 좋아요 수 (비정규화) |
| created_at | TIMESTAMPTZ | NO | now() | 생성 시간 |
| updated_at | TIMESTAMPTZ | NO | now() | 수정 시간 |
| is_deleted | BOOLEAN | NO | false | 소프트 삭제 |

#### post_media

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid_generate_v4() | PK |
| post_id | UUID | NO | - | FK to posts |
| media_type | ENUM | NO | - | IMAGE or VIDEO |
| url | VARCHAR(1000) | NO | - | S3/CloudFront URL |
| thumbnail_url | VARCHAR(1000) | YES | - | 비디오 썸네일 URL |
| original_filename | VARCHAR(255) | YES | - | 원본 파일명 |
| file_size | INTEGER | YES | - | 파일 크기 (bytes) |
| duration | INTEGER | YES | - | 비디오 길이 (초, 최대 60) |
| width | INTEGER | YES | - | 너비 (픽셀) |
| height | INTEGER | YES | - | 높이 (픽셀) |
| order | INTEGER | NO | 0 | 표시 순서 |
| created_at | TIMESTAMPTZ | NO | now() | 생성 시간 |

#### post_likes

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid_generate_v4() | PK |
| post_id | UUID | NO | - | FK to posts |
| user_id | VARCHAR(25) | NO | - | FK to users |
| created_at | TIMESTAMPTZ | NO | now() | 좋아요 시간 |

**Constraints**: `UNIQUE (post_id, user_id)` - 중복 좋아요 방지

---

## API 엔드포인트

### Post CRUD

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/posts` | Required | 게시글 작성 (미디어 첨부 가능) |
| GET | `/api/v1/posts` | Optional | 게시글 목록 조회 (페이지네이션) |
| GET | `/api/v1/posts/{post_id}` | Optional | 게시글 상세 조회 |
| PATCH | `/api/v1/posts/{post_id}` | Required (Owner) | 게시글 수정 |
| DELETE | `/api/v1/posts/{post_id}` | Required (Owner) | 게시글 소프트 삭제 |
| DELETE | `/api/v1/posts/{post_id}/hard` | Required (Admin) | 게시글 완전 삭제 |

### Like

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/posts/{post_id}/like` | Required | 좋아요 추가 |
| DELETE | `/api/v1/posts/{post_id}/like` | Required | 좋아요 취소 |
| GET | `/api/v1/posts/{post_id}/likes` | - | 좋아요한 사용자 목록 |

### Media

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/v1/posts/{post_id}/media` | Required (Owner) | 미디어 추가 |
| DELETE | `/api/v1/posts/{post_id}/media/{media_id}` | Required (Owner) | 미디어 삭제 |

---

## 서비스 레이어

### PostService

```python
class PostService:
    async def create_post(user_id, title, content) -> Post
    async def get_post(post_id) -> Post | None
    async def get_post_with_comments(post_id) -> Post | None
    async def list_posts(limit, offset, user_id?) -> Sequence[Post]
    async def update_post(post_id, user_id, title?, content?) -> Post | None
    async def delete_post(post_id, user_id) -> bool
```

### PostMediaService

```python
class PostMediaService:
    async def add_media_to_post(post_id, media_type, url, ...) -> PostMedia
    async def add_multiple_media_to_post(post_id, media_data_list) -> list[PostMedia]
    async def get_post_media(post_id) -> Sequence[PostMedia]
    async def get_media_by_id(media_id) -> PostMedia | None
    async def delete_media(media_id) -> bool
    async def delete_all_post_media(post_id) -> int
    async def reorder_media(post_id, media_order) -> list[PostMedia]
    async def get_media_count(post_id) -> int
```

### PostLikeService

```python
class PostLikeService:
    async def like_post(post_id, user_id) -> LikeResult
    async def unlike_post(post_id, user_id) -> LikeResult
    async def toggle_like(post_id, user_id) -> LikeResult
    async def is_liked_by_user(post_id, user_id) -> bool
    async def get_like_count(post_id) -> int
    async def get_post_likers(post_id, limit, offset) -> Sequence[PostLike]
    async def get_user_liked_posts(user_id, limit, offset) -> Sequence[PostLike]
    async def get_like_status_for_posts(post_ids, user_id) -> dict[UUID, bool]
```

---

## 미디어 업로드 (S3)

### 업로드 흐름

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Media Upload Flow                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

  [1] 클라이언트가 S3에 직접 업로드 (Presigned URL 사용 권장)
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                                                                             │
  │   1. GET /api/v1/upload/presigned-url  (미구현 - 추후 구현 필요)            │
  │      → 백엔드가 S3 presigned URL 발급                                       │
  │                                                                             │
  │   2. 클라이언트가 presigned URL로 S3에 직접 업로드                          │
  │                                                                             │
  │   3. POST /api/v1/posts                                                     │
  │      → 게시글 생성 + S3 URL 전달                                            │
  │                                                                             │
  └─────────────────────────────────────────────────────────────────────────────┘

  S3 Bucket Structure:
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │   AWS S3 Bucket                                                             │
  │   └── posts/                                                                │
  │       └── {post_id}/                                                        │
  │           ├── {uuid}.jpg        (원본 이미지)                               │
  │           ├── {uuid}_thumb.jpg  (썸네일)                                    │
  │           └── {uuid}.mp4        (비디오)                                    │
  └─────────────────────────────────────────────────────────────────────────────┘
```

### 제약 사항

| 항목 | 제한 |
|------|------|
| 이미지 크기 | 최대 10MB |
| 비디오 크기 | 최대 100MB |
| 비디오 길이 | 최대 60초 |
| 지원 포맷 (이미지) | JPEG, PNG, GIF, WebP |
| 지원 포맷 (비디오) | MP4, WebM |

### 미디어 메타데이터

미디어 업로드 시 다음 정보를 저장합니다:

```json
{
  "media_type": "IMAGE | VIDEO",
  "url": "https://cdn.example.com/posts/{post_id}/{uuid}.jpg",
  "thumbnail_url": "https://cdn.example.com/posts/{post_id}/{uuid}_thumb.jpg",
  "original_filename": "my_photo.jpg",
  "file_size": 1234567,
  "width": 1920,
  "height": 1080,
  "duration": 45,  // 비디오만
  "order": 0       // 표시 순서
}
```

---

## 좋아요 시스템

### 좋아요 흐름

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  Like Flow                                       │
└─────────────────────────────────────────────────────────────────────────────────┘

  좋아요 추가                                    좋아요 취소
  ┌─────────────────────────────┐              ┌─────────────────────────────┐
  │                             │              │                             │
  │  POST /posts/{id}/like      │              │  DELETE /posts/{id}/like    │
  │                             │              │                             │
  │  1. 중복 체크               │              │  1. 존재 확인               │
  │  2. PostLike 레코드 생성    │              │  2. PostLike 레코드 삭제    │
  │  3. Post.like_count += 1    │              │  3. Post.like_count -= 1    │
  │  4. 결과 반환               │              │  4. 결과 반환               │
  │                             │              │                             │
  └─────────────────────────────┘              └─────────────────────────────┘

  Response:
  {
    "success": true,
    "is_liked": true,
    "like_count": 42,
    "message": "Post liked successfully"
  }
```

### 비정규화 (like_count)

`Post.like_count`는 성능을 위해 비정규화되어 있습니다:

- **장점**: 게시글 목록 조회 시 COUNT 쿼리 불필요
- **단점**: PostLike 테이블과 동기화 필요
- **동기화**: 좋아요 추가/삭제 시 자동으로 증감

### N+1 문제 방지

게시글 목록에서 사용자의 좋아요 상태를 조회할 때 N+1 문제를 방지하기 위해
일괄 조회 메서드를 제공합니다:

```python
# 여러 게시글의 좋아요 상태를 한 번의 쿼리로 조회
like_status = await like_service.get_like_status_for_posts(
    post_ids=[uuid1, uuid2, uuid3],
    user_id="user123"
)
# 결과: {uuid1: True, uuid2: False, uuid3: True}
```

---

## 다음 단계 (TODO)

### 미구현 기능

1. **S3 Presigned URL 엔드포인트**
   - `GET /api/v1/upload/presigned-url`
   - 클라이언트가 S3에 직접 업로드할 수 있도록 presigned URL 발급

2. **S3 파일 삭제**
   - 미디어 삭제 시 S3의 실제 파일도 함께 삭제

3. **이미지 리사이징/썸네일 생성**
   - Lambda 또는 백엔드에서 이미지 처리

4. **비디오 트랜스코딩**
   - AWS Elemental MediaConvert 또는 ffmpeg 사용

### 환경 변수 (추가 필요)

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=
CLOUDFRONT_DOMAIN=  # Optional
```

---

*최종 수정: 2026-01-28*
