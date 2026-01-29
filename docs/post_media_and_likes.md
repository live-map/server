# Post Media & Likes Feature

이 문서는 게시글에 미디어(이미지/비디오)와 좋아요 기능을 추가하기 위한 모델 수정 내용을 설명합니다.

---

## 아키텍처 개요

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              Post Media & Likes Architecture                             │
└──────────────────────────────────────────────────────────────────────────────────────────┘

                                    DATA MODEL
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │                              ┌─────────────┐                                        │
  │                              │    User     │                                        │
  │                              │             │                                        │
  │                              │  id (CUID)  │                                        │
  │                              │  name       │                                        │
  │                              │  email      │                                        │
  │                              └──────┬──────┘                                        │
  │                                     │                                               │
  │                    ┌────────────────┼────────────────┐                              │
  │                    │                │                │                              │
  │                    ▼                ▼                ▼                              │
  │             ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                       │
  │             │    Post     │  │  PostLike   │  │   Comment   │                       │
  │             │             │  │             │  │             │                       │
  │             │  id (UUID)  │◀─│  post_id    │  │  post_id    │                       │
  │             │  user_id    │  │  user_id    │  │  user_id    │                       │
  │             │  title      │  │  created_at │  │  content    │                       │
  │             │  content    │  └─────────────┘  └─────────────┘                       │
  │             │  like_count │                                                         │
  │             └──────┬──────┘                                                         │
  │                    │                                                                │
  │                    ▼                                                                │
  │             ┌─────────────┐                                                         │
  │             │  PostMedia  │                                                         │
  │             │             │                                                         │
  │             │  id (UUID)  │                                                         │
  │             │  post_id    │  (FK to Post)                                           │
  │             │  media_type │  (IMAGE/VIDEO)                                          │
  │             │  url        │  (S3/CloudFront URL)                                    │
  │             │  thumbnail  │  (비디오 썸네일)                                         │
  │             │  duration   │  (비디오 길이, 최대 60초)                                │
  │             └─────────────┘                                                         │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 미디어 업로드 흐름 (예정)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                  Media Upload Flow                                       │
└──────────────────────────────────────────────────────────────────────────────────────────┘

  [1] 클라이언트가 파일을 백엔드로 전송
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │   POST /api/v1/posts/{post_id}/media                                                │
  │   Content-Type: multipart/form-data                                                 │
  │   Authorization: Bearer <token>                                                     │
  │                                                                                     │
  │   Body: file (image/video)                                                          │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
  [2] 백엔드가 파일 검증
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │   - 파일 타입 확인 (image/jpeg, image/png, video/mp4 등)                            │
  │   - 파일 크기 제한 (이미지: 10MB, 비디오: 100MB)                                    │
  │   - 비디오 길이 제한 (최대 60초)                                                    │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
  [3] 백엔드가 S3에 업로드
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │   AWS S3 Bucket                                                                     │
  │   └── posts/                                                                        │
  │       └── {post_id}/                                                                │
  │           ├── {uuid}.jpg        (원본 이미지)                                       │
  │           ├── {uuid}_thumb.jpg  (썸네일)                                            │
  │           └── {uuid}.mp4        (비디오)                                            │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
  [4] DB에 메타데이터 저장
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │   PostMedia {                                                                       │
  │     id: "uuid",                                                                     │
  │     post_id: "post-uuid",                                                           │
  │     media_type: "IMAGE" | "VIDEO",                                                  │
  │     url: "https://cdn.example.com/posts/{post_id}/{uuid}.jpg",                      │
  │     thumbnail_url: "https://cdn.example.com/posts/{post_id}/{uuid}_thumb.jpg",      │
  │     file_size: 1234567,                                                             │
  │     width: 1920,                                                                    │
  │     height: 1080,                                                                   │
  │     duration: 45  // 비디오만                                                       │
  │   }                                                                                 │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
                                            │
                                            ▼
  [5] 프론트엔드가 CloudFront URL로 미디어 표시
  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                     │
  │   <img src="https://cdn.example.com/posts/{post_id}/{uuid}.jpg" />                  │
  │   <video src="https://cdn.example.com/posts/{post_id}/{uuid}.mp4" />                │
  │                                                                                     │
  └─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 좋아요 흐름 (예정)

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                                     Like Flow                                            │
└──────────────────────────────────────────────────────────────────────────────────────────┘

  좋아요 추가                                    좋아요 취소
  ┌─────────────────────────────┐              ┌─────────────────────────────┐
  │                             │              │                             │
  │  POST /posts/{id}/like      │              │  DELETE /posts/{id}/like    │
  │                             │              │                             │
  │  1. PostLike 레코드 생성    │              │  1. PostLike 레코드 삭제    │
  │  2. Post.like_count += 1    │              │  2. Post.like_count -= 1    │
  │                             │              │                             │
  └─────────────────────────────┘              └─────────────────────────────┘

  중복 방지: (post_id, user_id) UNIQUE 제약조건
```

---

## 새로 생성된 파일

### 1. PostMedia 모델

**파일**: `server/app/models/post_media.py`

```python
"""
PostMedia model for storing media files attached to posts.
"""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post


class MediaType(str, enum.Enum):
    """미디어 타입."""
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class PostMedia(Base):
    """
    게시글 미디어 모델.

    게시글에 첨부된 이미지 또는 비디오 파일 정보를 저장합니다.
    파일은 S3에 저장되고, 이 모델은 URL과 메타데이터만 저장합니다.
    """

    __tablename__ = "post_media"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Post
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Media type
    media_type: Mapped[MediaType] = mapped_column(
        Enum(MediaType, name="media_type_enum"),
        nullable=False,
    )

    # URLs
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # File metadata
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)  # bytes
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)   # seconds (max 60)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)      # pixels
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)     # pixels

    # Display order (for multiple media)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="media")
```

### 2. PostLike 모델

**파일**: `server/app/models/post_like.py`

```python
"""
PostLike model for tracking user likes on posts.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class PostLike(Base):
    """
    게시글 좋아요 모델.

    어떤 사용자가 어떤 게시글에 좋아요를 눌렀는지 추적합니다.
    (post_id, user_id) 조합은 unique하여 중복 좋아요를 방지합니다.
    """

    __tablename__ = "post_likes"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Post
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Foreign key to User
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="likes")
    user: Mapped["User"] = relationship("User", back_populates="post_likes")

    # Unique constraint to prevent duplicate likes
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like_post_user"),
    )
```

---

## 수정된 파일

### 1. Post 모델

**파일**: `server/app/models/post.py`

**변경 사항**:

```diff
+ from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
- from sqlalchemy import DateTime, ForeignKey, String, Text, func

  if TYPE_CHECKING:
      from app.models.comment import Comment
+     from app.models.post_like import PostLike
+     from app.models.post_media import PostMedia
      from app.models.user import User

  # Post content
  title: Mapped[str] = mapped_column(String(200), nullable=False)
  content: Mapped[str] = mapped_column(Text, nullable=False)

+ # Like count (denormalized for performance)
+ like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

  # Relationships
  user: Mapped["User"] = relationship("User", back_populates="posts")
  comments: Mapped[list["Comment"]] = relationship(...)
+ media: Mapped[list["PostMedia"]] = relationship(
+     "PostMedia",
+     back_populates="post",
+     cascade="all, delete-orphan",
+     order_by="PostMedia.order",
+ )
+ likes: Mapped[list["PostLike"]] = relationship(
+     "PostLike",
+     back_populates="post",
+     cascade="all, delete-orphan",
+ )
```

### 2. User 모델

**파일**: `server/app/models/user.py`

**변경 사항**:

```diff
  if TYPE_CHECKING:
      from app.models.account import Account
      from app.models.comment import Comment
      from app.models.item import Item
      from app.models.post import Post
+     from app.models.post_like import PostLike
      from app.models.session import Session

  # Relationships
  comments: Mapped[list["Comment"]] = relationship(...)
+ post_likes: Mapped[list["PostLike"]] = relationship(
+     "PostLike", back_populates="user", cascade="all, delete-orphan"
+ )
```

### 3. models/__init__.py

**파일**: `server/app/models/__init__.py`

**변경 사항**:

```diff
  from app.models.post import Post
+ from app.models.post_media import MediaType, PostMedia
+ from app.models.post_like import PostLike
  from app.models.comment import Comment

  __all__ = [
      "Post",
+     "PostMedia",
+     "PostLike",
+     "MediaType",
      "Comment",
      ...
  ]
```

---

## Prisma 스키마 변경

**파일**: `client/prisma/schema.prisma`

### 새로운 Enum

```prisma
enum MediaType {
  IMAGE
  VIDEO
}
```

### Post 모델 수정

```prisma
model Post {
  id        String   @id @default(uuid()) @db.Uuid
  userId    String   @map("user_id") @db.VarChar(25)
  title     String   @db.VarChar(200)
  content   String   @db.Text
+ likeCount Int      @default(0) @map("like_count")
  createdAt DateTime @default(now()) @map("created_at")
  updatedAt DateTime @updatedAt @map("updated_at")
  isDeleted Boolean  @default(false) @map("is_deleted")

  // Relations
  user     User        @relation(fields: [userId], references: [id], onDelete: Cascade)
  comments Comment[]
+ media    PostMedia[]
+ likes    PostLike[]

  @@index([userId])
  @@map("posts")
}
```

### User 모델 수정

```prisma
model User {
  ...
  posts     Post[]
  comments  Comment[]
+ postLikes PostLike[]
  ...
}
```

### 새로운 PostMedia 모델

```prisma
model PostMedia {
  id               String    @id @default(uuid()) @db.Uuid
  postId           String    @map("post_id") @db.Uuid
  mediaType        MediaType @map("media_type")
  url              String    @db.VarChar(1000)
  thumbnailUrl     String?   @map("thumbnail_url") @db.VarChar(1000)
  originalFilename String?   @map("original_filename") @db.VarChar(255)
  fileSize         Int?      @map("file_size")    // bytes
  duration         Int?                           // seconds (video only, max 60)
  width            Int?                           // pixels
  height           Int?                           // pixels
  order            Int       @default(0)          // display order
  createdAt        DateTime  @default(now()) @map("created_at")

  // Relations
  post Post @relation(fields: [postId], references: [id], onDelete: Cascade)

  @@index([postId])
  @@map("post_media")
}
```

### 새로운 PostLike 모델

```prisma
model PostLike {
  id        String   @id @default(uuid()) @db.Uuid
  postId    String   @map("post_id") @db.Uuid
  userId    String   @map("user_id") @db.VarChar(25)
  createdAt DateTime @default(now()) @map("created_at")

  // Relations
  post Post @relation(fields: [postId], references: [id], onDelete: Cascade)
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([postId, userId], name: "uq_post_like_post_user")
  @@index([postId])
  @@index([userId])
  @@map("post_likes")
}
```

---

## 데이터베이스 테이블

### post_media 테이블

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid_generate_v4() | PK |
| post_id | UUID | NO | - | FK to posts |
| media_type | media_type_enum | NO | - | IMAGE or VIDEO |
| url | VARCHAR(1000) | NO | - | S3/CloudFront URL |
| thumbnail_url | VARCHAR(1000) | YES | - | 비디오 썸네일 URL |
| original_filename | VARCHAR(255) | YES | - | 원본 파일명 |
| file_size | INTEGER | YES | - | 파일 크기 (bytes) |
| duration | INTEGER | YES | - | 비디오 길이 (초, 최대 60) |
| width | INTEGER | YES | - | 너비 (픽셀) |
| height | INTEGER | YES | - | 높이 (픽셀) |
| order | INTEGER | NO | 0 | 표시 순서 |
| created_at | TIMESTAMPTZ | NO | now() | 생성 시간 |

**인덱스**:
- `ix_post_media_post_id` on (post_id)

### post_likes 테이블

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| id | UUID | NO | uuid_generate_v4() | PK |
| post_id | UUID | NO | - | FK to posts |
| user_id | VARCHAR(25) | NO | - | FK to users |
| created_at | TIMESTAMPTZ | NO | now() | 좋아요 시간 |

**인덱스**:
- `ix_post_likes_post_id` on (post_id)
- `ix_post_likes_user_id` on (user_id)

**제약조건**:
- `uq_post_like_post_user` UNIQUE (post_id, user_id)

### posts 테이블 변경

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| ... | ... | ... | ... | 기존 컬럼들 |
| like_count | INTEGER | NO | 0 | 좋아요 수 (비정규화) |

---

## 다음 단계 (구현 예정)

### 1. S3 업로드 서비스

```
server/app/api/v1/post/media_service.py
- upload_to_s3(file, post_id) -> S3 URL
- delete_from_s3(url)
- generate_thumbnail(video_url) -> thumbnail URL
```

### 2. 환경 변수

```env
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
AWS_REGION=
CLOUDFRONT_DOMAIN=  # Optional
```

### 3. API 엔드포인트

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | /posts/{post_id}/media | 미디어 업로드 | Required |
| DELETE | /posts/{post_id}/media/{media_id} | 미디어 삭제 | Required |
| POST | /posts/{post_id}/like | 좋아요 | Required |
| DELETE | /posts/{post_id}/like | 좋아요 취소 | Required |
| GET | /posts/{post_id}/likes | 좋아요 한 사용자 목록 | - |

### 4. Repository 메서드

```python
# PostMediaRepository
- create(media: PostMedia) -> PostMedia
- get_by_post_id(post_id: UUID) -> list[PostMedia]
- delete(media_id: UUID) -> bool

# PostLikeRepository
- create(like: PostLike) -> PostLike
- delete(post_id: UUID, user_id: str) -> bool
- get_by_post_id(post_id: UUID, limit, offset) -> list[PostLike]
- exists(post_id: UUID, user_id: str) -> bool
- increment_like_count(post_id: UUID)
- decrement_like_count(post_id: UUID)
```

### 5. 프론트엔드 업데이트

- `lib/api.ts`에 미디어/좋아요 API 래퍼 추가
- `pnpm generate:openapi-ts`로 타입 재생성
- 게시글 작성/수정 폼에 미디어 업로드 UI 추가
- 게시글 목록/상세에 좋아요 버튼 추가

---

## 제약 사항

### 미디어 제약

- **이미지**: 최대 10MB, 지원 포맷 (JPEG, PNG, GIF, WebP)
- **비디오**: 최대 100MB, 최대 60초, 지원 포맷 (MP4, WebM)
- **게시글당**: 이미지와 비디오 모두 첨부 가능 (다중 미디어)

### 좋아요 제약

- 사용자당 게시글에 1번만 좋아요 가능 (UNIQUE 제약조건)
- 자신의 게시글에도 좋아요 가능
- `like_count`는 성능을 위해 비정규화 (PostLike 테이블과 동기화 필요)
