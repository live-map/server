# API Endpoints Documentation

Post, Media, Like API 엔드포인트에 대한 상세 문서입니다.

---

## 목차

1. [인증](#인증)
2. [Post Endpoints](#post-endpoints)
3. [Like Endpoints](#like-endpoints)
4. [Media Endpoints](#media-endpoints)
5. [Response Schemas](#response-schemas)

---

## 인증

### CurrentUser (Required)
- JWT 토큰 필수
- `Authorization: Bearer <token>` 헤더 필요

### CurrentUserOptional (Optional)
- JWT 토큰 선택
- 인증 시 추가 정보 제공 (예: `is_liked`)

### CurrentAdmin (Admin Only)
- JWT 토큰 필수 + `role: "ADMIN"` 필요

---

## Post Endpoints

### POST /api/v1/posts

게시글 작성 (미디어 첨부 가능)

**Auth**: Required

**Request Body**:
```json
{
  "title": "게시글 제목",
  "content": "게시글 내용",
  "media": [
    {
      "media_type": "IMAGE",
      "url": "https://cdn.example.com/posts/xxx/image.jpg",
      "thumbnail_url": null,
      "original_filename": "my_photo.jpg",
      "file_size": 123456,
      "duration": null,
      "width": 1920,
      "height": 1080,
      "order": 0
    }
  ]
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "clxxxxx",
  "user_name": null,
  "title": "게시글 제목",
  "content": "게시글 내용",
  "like_count": 0,
  "is_liked": false,
  "media": [
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "post_id": "550e8400-e29b-41d4-a716-446655440000",
      "media_type": "IMAGE",
      "url": "https://cdn.example.com/posts/xxx/image.jpg",
      "thumbnail_url": null,
      "original_filename": "my_photo.jpg",
      "file_size": 123456,
      "duration": null,
      "width": 1920,
      "height": 1080,
      "order": 0,
      "created_at": "2026-01-28T12:00:00Z"
    }
  ],
  "created_at": "2026-01-28T12:00:00Z",
  "updated_at": "2026-01-28T12:00:00Z",
  "comment_count": 0
}
```

---

### GET /api/v1/posts

게시글 목록 조회

**Auth**: Optional (인증 시 `is_liked` 포함)

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | 최대 조회 수 (1-100) |
| offset | int | 0 | 건너뛸 수 |

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "clxxxxx",
      "user_name": "홍길동",
      "title": "게시글 제목",
      "content": "게시글 내용",
      "like_count": 42,
      "is_liked": true,
      "media": [...],
      "created_at": "2026-01-28T12:00:00Z",
      "updated_at": "2026-01-28T12:00:00Z",
      "comment_count": 5
    }
  ],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

---

### GET /api/v1/posts/{post_id}

게시글 상세 조회

**Auth**: Optional (인증 시 `is_liked` 포함)

**Path Parameters**:
| Param | Type | Description |
|-------|------|-------------|
| post_id | UUID | 게시글 UUID |

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "clxxxxx",
  "user_name": "홍길동",
  "title": "게시글 제목",
  "content": "게시글 내용",
  "like_count": 42,
  "is_liked": false,
  "media": [...],
  "created_at": "2026-01-28T12:00:00Z",
  "updated_at": "2026-01-28T12:00:00Z",
  "comment_count": 5
}
```

**Error** (404 Not Found):
```json
{
  "detail": "Post not found"
}
```

---

### PATCH /api/v1/posts/{post_id}

게시글 수정

**Auth**: Required (Owner only)

**Request Body**:
```json
{
  "title": "수정된 제목",
  "content": "수정된 내용"
}
```

**Response** (200 OK): PostResponse

**Error** (403 Forbidden):
```json
{
  "detail": "You are not the owner of this post"
}
```

---

### DELETE /api/v1/posts/{post_id}

게시글 소프트 삭제

**Auth**: Required (Owner only)

**Response** (204 No Content)

---

### DELETE /api/v1/posts/{post_id}/hard

게시글 완전 삭제 (Admin Only)

**Auth**: Required (Admin only)

**Response** (204 No Content)

**Note**: CASCADE로 모든 댓글, 미디어, 좋아요도 함께 삭제됩니다.

---

## Like Endpoints

### POST /api/v1/posts/{post_id}/like

게시글 좋아요

**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "is_liked": true,
  "like_count": 43,
  "message": "Post liked successfully"
}
```

**이미 좋아요한 경우**:
```json
{
  "success": false,
  "is_liked": true,
  "like_count": 43,
  "message": "Already liked this post"
}
```

---

### DELETE /api/v1/posts/{post_id}/like

게시글 좋아요 취소

**Auth**: Required

**Response** (200 OK):
```json
{
  "success": true,
  "is_liked": false,
  "like_count": 42,
  "message": "Post unliked successfully"
}
```

**좋아요하지 않은 경우**:
```json
{
  "success": false,
  "is_liked": false,
  "like_count": 42,
  "message": "Not liked this post"
}
```

---

### GET /api/v1/posts/{post_id}/likes

게시글을 좋아요한 사용자 목록

**Auth**: Not required

**Query Parameters**:
| Param | Type | Default | Description |
|-------|------|---------|-------------|
| limit | int | 20 | 최대 조회 수 (1-100) |
| offset | int | 0 | 건너뛸 수 |

**Response** (200 OK):
```json
{
  "items": [
    {
      "user_id": "clxxxxx",
      "user_name": "홍길동",
      "user_image": "https://example.com/avatar.jpg",
      "liked_at": "2026-01-28T12:00:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

## Media Endpoints

### POST /api/v1/posts/{post_id}/media

게시글에 미디어 추가

**Auth**: Required (Owner only)

**Request Body**:
```json
{
  "media_type": "VIDEO",
  "url": "https://cdn.example.com/posts/xxx/video.mp4",
  "thumbnail_url": "https://cdn.example.com/posts/xxx/video_thumb.jpg",
  "original_filename": "my_video.mp4",
  "file_size": 12345678,
  "duration": 45,
  "width": 1920,
  "height": 1080,
  "order": 1
}
```

**Response** (201 Created):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "post_id": "550e8400-e29b-41d4-a716-446655440000",
  "media_type": "VIDEO",
  "url": "https://cdn.example.com/posts/xxx/video.mp4",
  "thumbnail_url": "https://cdn.example.com/posts/xxx/video_thumb.jpg",
  "original_filename": "my_video.mp4",
  "file_size": 12345678,
  "duration": 45,
  "width": 1920,
  "height": 1080,
  "order": 1,
  "created_at": "2026-01-28T12:00:00Z"
}
```

---

### DELETE /api/v1/posts/{post_id}/media/{media_id}

게시글 미디어 삭제

**Auth**: Required (Owner only)

**Response** (204 No Content)

**Note**: S3의 실제 파일은 별도로 삭제해야 합니다.

---

## Response Schemas

### PostResponse

```typescript
interface PostResponse {
  id: string;           // UUID
  user_id: string;      // CUID
  user_name?: string;
  title: string;
  content: string;
  like_count: number;
  is_liked: boolean;    // 현재 사용자의 좋아요 여부
  media: PostMediaResponse[];
  created_at: string;   // ISO 8601
  updated_at: string;   // ISO 8601
  comment_count: number;
}
```

### PostMediaResponse

```typescript
interface PostMediaResponse {
  id: string;           // UUID
  post_id: string;      // UUID
  media_type: "IMAGE" | "VIDEO";
  url: string;
  thumbnail_url?: string;
  original_filename?: string;
  file_size?: number;   // bytes
  duration?: number;    // seconds (video only)
  width?: number;       // pixels
  height?: number;      // pixels
  order: number;
  created_at: string;   // ISO 8601
}
```

### LikeResponse

```typescript
interface LikeResponse {
  success: boolean;
  is_liked: boolean;
  like_count: number;
  message: string;
}
```

### PostLikerResponse

```typescript
interface PostLikerResponse {
  user_id: string;
  user_name?: string;
  user_image?: string;
  liked_at: string;     // ISO 8601
}
```

---

*최종 수정: 2026-01-28*
