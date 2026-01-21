# 게시판 및 대댓글(Nested Reply) 시스템 구현 가이드

이 문서는 FastAPI + SQLAlchemy를 사용하여 게시판(Post)과 무한 대댓글(Nested Comment) 시스템을 구현하는 방법을 설명합니다.

## 목차

1. [개요](#1-개요)
2. [데이터베이스 설계](#2-데이터베이스-설계)
3. [Model (SQLAlchemy Entity)](#3-model-sqlalchemy-entity)
4. [Repository Layer](#4-repository-layer)
5. [Service Layer](#5-service-layer)
6. [Schemas (Pydantic)](#6-schemas-pydantic)
7. [API Endpoints](#7-api-endpoints)
8. [사용 예시](#8-사용-예시)
9. [코드 간 상호작용 및 데이터 흐름 상세 설명](#9-코드-간-상호작용-및-데이터-흐름-상세-설명)
   - [9.1 전체 아키텍처 흐름](#91-전체-아키텍처-흐름)
   - [9.2 Model 간 상호작용 상세](#92-model-간-상호작용-상세)
   - [9.3 Controller → Service → Repository 데이터 흐름](#93-controller--service--repository-데이터-흐름)
   - [9.4 depth와 order_number의 역할](#94-depth와-order_number의-역할)
   - [9.5 트리 구조 변환 로직 상세](#95-트리-구조-변환-로직-상세)
   - [9.6 의존성 주입 체인](#96-의존성-주입-체인)
   - [9.7 Soft Delete가 대댓글 구조에 미치는 영향](#97-soft-delete가-대댓글-구조에-미치는-영향)
   - [9.8 Cascade 삭제 동작](#98-cascade-삭제-동작)

---

## 1. 개요

### 요구사항

- 사용자가 게시글(Post)을 작성할 수 있음
- 게시글에 댓글(Comment)을 달 수 있음
- 댓글에 대댓글(Reply to Comment)을 무한히 달 수 있음

### 핵심 설계: Self-Join 패턴

대댓글을 구현하는 가장 효율적인 방법은 **Self-Join (자기 참조)** 패턴입니다:

```
Post (게시글)
  └── Comment (댓글, depth=0)
        └── Comment (대댓글, depth=1)
              └── Comment (대대댓글, depth=2)
                    └── ... (무한 중첩 가능)
```

각 댓글은:
- 반드시 하나의 **게시글(Post)**에 소속됨
- 선택적으로 **부모 댓글(Parent Comment)**을 가질 수 있음 (대댓글인 경우)

---

## 2. 데이터베이스 설계

### ERD (Entity Relationship Diagram)

```
┌─────────────────────┐
│        users        │
├─────────────────────┤
│ id (PK, UUID)       │
│ name                │
│ email               │
│ ...                 │
└─────────────────────┘
        │
        │
        ├──────────────────────────────────────┐
        │                                      │
        │ 1:N                                  │ 1:N
        │ (user_id FK)                         │ (user_id FK)
        ▼                                      ▼
┌─────────────────────┐              ┌──────────────────────────┐
│        posts        │              │         comments         │
├─────────────────────┤              ├──────────────────────────┤
│ id (PK, UUID)       │◄─────────────│ post_id (FK, UUID)       │
│ user_id (FK, UUID)  │     1:N      │ id (PK, UUID)            │
│ title               │              │ user_id (FK, UUID)       │
│ content             │              │ parent_id (FK, UUID,NULL)│───┐
│ created_at          │              │ content                  │   │
│ updated_at          │              │ depth                    │   │ 1:N
└─────────────────────┘              │ order_number             │   │ Self-Join
                                     │ created_at               │   │ (자기 참조)
                                     │ updated_at               │   │
                                     │ is_deleted               │◄──┘
                                     └──────────────────────────┘
```

**관계 설명 (4개의 1:N 관계):**

| 관계 | FK 위치 | 타입 | 설명 |
|------|---------|------|------|
| users → posts | posts.user_id | UUID | 한 유저가 여러 게시글 작성 가능 |
| users → comments | comments.user_id | UUID | 한 유저가 여러 댓글 작성 가능 |
| posts → comments | comments.post_id | UUID | 한 게시글에 여러 댓글 가능 |
| comments → comments | comments.parent_id | UUID (nullable) | Self-Join으로 무한 대댓글 구조 |

**UUID 사용 이유:**
- 분산 시스템에서 ID 충돌 방지
- 보안: ID 예측 불가능 (sequential ID는 추측 가능)
- 데이터베이스 마이그레이션 용이

### 주요 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `post_id` | FK | 댓글이 속한 게시글 (항상 필수) |
| `parent_id` | FK (nullable) | 부모 댓글 ID. NULL이면 최상위 댓글, 값이 있으면 대댓글 |
| `depth` | Integer | 댓글의 깊이. 최상위=0, 대댓글=1, 대대댓글=2, ... |
| `order_number` | Integer | 같은 그룹 내 정렬 순서 |
| `is_deleted` | Boolean | 소프트 삭제 여부 (삭제된 댓글도 대댓글이 있으면 구조 유지) |

---

## 3. Model (SQLAlchemy Entity)

프로젝트의 기존 패턴을 따라 `app/models/` 디렉토리에 모델을 정의합니다.

### 3.1 Post 모델 (`app/models/post.py`)

```python
"""
Post model for the bulletin board system.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.user import User


class Post(Base):
    """
    게시글 모델.

    사용자가 작성한 게시글을 저장합니다.
    각 게시글은 여러 댓글을 가질 수 있습니다.
    """

    __tablename__ = "posts"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to User (UUID)
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Post content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Soft delete
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="posts")
    comments: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Post(id={self.id}, title='{self.title[:20]}...')>"
```

### 3.2 Comment 모델 (`app/models/comment.py`)

```python
"""
Comment model with self-referencing relationship for nested replies.

This implements the self-join pattern where a comment can have:
- A parent post (required)
- A parent comment (optional, for replies)
- Multiple child comments (replies to this comment)
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.user import User


class Comment(Base):
    """
    댓글 모델 (Self-Join 패턴으로 대댓글 지원).

    주요 특징:
    - parent_id가 NULL이면 최상위 댓글
    - parent_id가 있으면 해당 댓글의 대댓글
    - depth로 계층 깊이 관리
    - order_number로 같은 그룹 내 정렬
    """

    __tablename__ = "comments"

    # Primary key - UUID
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Foreign key to Post (UUID - 필수, 모든 댓글은 게시글에 소속)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Foreign key to User (작성자)
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Self-referencing foreign key (UUID - 부모 댓글, 대댓글인 경우에만 값 있음)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,  # NULL이면 최상위 댓글
        index=True,
    )

    # Comment content
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Hierarchy information
    depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="댓글 깊이: 0=최상위, 1=대댓글, 2=대대댓글...",
    )
    order_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="같은 그룹 내 정렬 순서",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Soft delete (대댓글이 있는 경우 구조 유지를 위해 soft delete 사용)
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)

    # ========================================
    # Relationships
    # ========================================

    # 게시글과의 관계
    post: Mapped["Post"] = relationship("Post", back_populates="comments")

    # 작성자와의 관계
    user: Mapped["User"] = relationship("User", back_populates="comments")

    # Self-referencing relationships (대댓글 구조)
    # 부모 댓글 (이 댓글이 대댓글인 경우)
    parent: Mapped[Optional["Comment"]] = relationship(
        "Comment",
        remote_side=[id],  # 자기 참조 시 어느 쪽이 "1" 쪽인지 명시
        back_populates="replies",
        foreign_keys=[parent_id],
    )

    # 자식 댓글들 (이 댓글의 대댓글들)
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, post_id={self.post_id}, depth={self.depth})>"

    @property
    def is_reply(self) -> bool:
        """대댓글인지 여부."""
        return self.parent_id is not None

    @property
    def reply_count(self) -> int:
        """직접 대댓글 수 (lazy load 주의)."""
        return len(self.replies) if self.replies else 0
```

### 3.3 User 모델 업데이트 (관계 추가)

기존 `app/models/user.py`에 관계를 추가합니다:

```python
# 기존 imports에 추가
if TYPE_CHECKING:
    from app.models.post import Post
    from app.models.comment import Comment

class User(Base):
    # ... 기존 필드들 ...

    # 추가할 relationships
    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="user", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="user", cascade="all, delete-orphan"
    )
```

### 3.4 Models `__init__.py` 업데이트

```python
# app/models/__init__.py
from app.models.post import Post
from app.models.comment import Comment

__all__ = [
    # ... 기존 exports ...
    "Post",
    "Comment",
]
```

---

## 4. Repository Layer

Repository는 데이터베이스 접근 로직을 캡슐화합니다.

### 4.1 Post Repository (`app/api/v1/post/repository.py`)

```python
"""
Post Repository - Data access layer for Post model.

Handles all database operations for posts.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.post import Post

logger = logging.getLogger(__name__)


class PostRepository:
    """
    Repository for Post database operations.

    모든 메서드는 SQLAlchemy 2.0 async 문법을 사용합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, post: Post) -> Post:
        """
        새 게시글 생성.

        Args:
            post: 생성할 Post 엔티티

        Returns:
            생성된 Post (ID가 할당됨)
        """
        self.session.add(post)
        await self.session.flush()  # ID 할당을 위해 flush
        await self.session.refresh(post)
        logger.debug(f"Created post: {post.id}")
        return post

    async def get_by_id(self, post_id: uuid.UUID) -> Post | None:
        """
        ID로 게시글 조회.

        Args:
            post_id: 게시글 UUID

        Returns:
            Post | None: 게시글 또는 None
        """
        stmt = select(Post).where(Post.id == post_id, Post.is_deleted == False)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_comments(self, post_id: uuid.UUID) -> Post | None:
        """
        ID로 게시글 조회 (댓글 포함).

        Eager loading으로 댓글을 함께 로드합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            Post | None: 댓글이 포함된 게시글
        """
        stmt = (
            select(Post)
            .options(
                selectinload(Post.comments),  # 댓글 eager load
                selectinload(Post.user),      # 작성자 eager load
            )
            .where(Post.id == post_id, Post.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: str | None = None,
    ) -> Sequence[Post]:
        """
        게시글 목록 조회 (페이지네이션).

        Args:
            limit: 최대 조회 수
            offset: 건너뛸 수
            user_id: 특정 사용자의 글만 조회 (선택)

        Returns:
            Sequence[Post]: 게시글 목록
        """
        stmt = select(Post).where(Post.is_deleted == False)

        if user_id:
            stmt = stmt.where(Post.user_id == user_id)

        stmt = stmt.order_by(Post.created_at.desc()).limit(limit).offset(offset)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, post: Post) -> Post:
        """
        게시글 수정.

        Args:
            post: 수정할 Post 엔티티 (이미 변경된 상태)

        Returns:
            수정된 Post
        """
        await self.session.flush()
        await self.session.refresh(post)
        logger.debug(f"Updated post: {post.id}")
        return post

    async def soft_delete(self, post_id: uuid.UUID) -> bool:
        """
        게시글 소프트 삭제.

        Args:
            post_id: 삭제할 게시글 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        post = await self.get_by_id(post_id)
        if post is None:
            return False

        post.is_deleted = True
        await self.session.flush()
        logger.debug(f"Soft deleted post: {post_id}")
        return True

    async def count(self, user_id: str | None = None) -> int:
        """
        게시글 총 개수.

        Args:
            user_id: 특정 사용자의 글만 카운트 (선택)

        Returns:
            int: 게시글 수
        """
        stmt = select(func.count()).select_from(Post).where(Post.is_deleted == False)

        if user_id:
            stmt = stmt.where(Post.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one()
```

### 4.2 Comment Repository (`app/api/v1/post/comment_repository.py`)

```python
"""
Comment Repository - Data access layer for Comment model.

Handles all database operations for comments including nested replies.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.comment import Comment

logger = logging.getLogger(__name__)


class CommentRepository:
    """
    Repository for Comment database operations.

    대댓글 구조를 위한 Self-Join 쿼리를 처리합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, comment: Comment) -> Comment:
        """
        새 댓글/대댓글 생성.

        Args:
            comment: 생성할 Comment 엔티티

        Returns:
            생성된 Comment (ID 할당됨)
        """
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        logger.debug(f"Created comment: {comment.id}, depth: {comment.depth}")
        return comment

    async def get_by_id(self, comment_id: uuid.UUID) -> Comment | None:
        """
        ID로 댓글 조회.

        Args:
            comment_id: 댓글 UUID

        Returns:
            Comment | None
        """
        stmt = select(Comment).where(
            Comment.id == comment_id,
            Comment.is_deleted == False,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_id_with_replies(self, comment_id: uuid.UUID) -> Comment | None:
        """
        ID로 댓글 조회 (대댓글 포함).

        Args:
            comment_id: 댓글 UUID

        Returns:
            Comment | None: 대댓글이 포함된 댓글
        """
        stmt = (
            select(Comment)
            .options(
                selectinload(Comment.replies),  # 직접 대댓글 eager load
                selectinload(Comment.user),     # 작성자 eager load
            )
            .where(Comment.id == comment_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_top_level_comments(
        self,
        post_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Comment]:
        """
        게시글의 최상위 댓글만 조회 (depth=0, parent_id=NULL).

        대댓글은 별도로 로드하거나 eager loading 사용.

        Args:
            post_id: 게시글 UUID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[Comment]: 최상위 댓글 목록
        """
        stmt = (
            select(Comment)
            .options(
                selectinload(Comment.user),
                selectinload(Comment.replies).selectinload(Comment.user),
            )
            .where(
                Comment.post_id == post_id,
                Comment.parent_id == None,  # 최상위 댓글만
                Comment.is_deleted == False,
            )
            .order_by(Comment.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_comments_by_post(
        self,
        post_id: uuid.UUID,
        include_deleted: bool = False,
    ) -> Sequence[Comment]:
        """
        게시글의 모든 댓글 조회 (계층 구조 포함).

        order_number와 depth로 정렬하여 계층 순서대로 반환.

        Args:
            post_id: 게시글 UUID
            include_deleted: 삭제된 댓글 포함 여부

        Returns:
            Sequence[Comment]: 모든 댓글 (계층 순서)
        """
        conditions = [Comment.post_id == post_id]

        if not include_deleted:
            conditions.append(Comment.is_deleted == False)

        stmt = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(and_(*conditions))
            .order_by(
                Comment.order_number.asc(),  # 그룹 순서
                Comment.depth.asc(),         # 깊이 순서
                Comment.created_at.asc(),    # 생성 시간
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_replies(
        self,
        parent_id: uuid.UUID,
        limit: int = 50,
    ) -> Sequence[Comment]:
        """
        특정 댓글의 직접 대댓글만 조회.

        Args:
            parent_id: 부모 댓글 UUID
            limit: 최대 조회 수

        Returns:
            Sequence[Comment]: 대댓글 목록
        """
        stmt = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(
                Comment.parent_id == parent_id,
                Comment.is_deleted == False,
            )
            .order_by(Comment.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_next_order_number(self, post_id: uuid.UUID) -> int:
        """
        새 최상위 댓글의 order_number 계산.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 다음 order_number
        """
        stmt = (
            select(func.coalesce(func.max(Comment.order_number), 0))
            .where(Comment.post_id == post_id)
        )
        result = await self.session.execute(stmt)
        max_order = result.scalar_one()
        return max_order + 1

    async def update(self, comment: Comment) -> Comment:
        """
        댓글 수정.

        Args:
            comment: 수정할 Comment 엔티티

        Returns:
            수정된 Comment
        """
        await self.session.flush()
        await self.session.refresh(comment)
        logger.debug(f"Updated comment: {comment.id}")
        return comment

    async def soft_delete(self, comment_id: uuid.UUID) -> bool:
        """
        댓글 소프트 삭제.

        대댓글이 있는 경우에도 구조 유지를 위해 soft delete 사용.

        Args:
            comment_id: 삭제할 댓글 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        comment = await self.get_by_id(comment_id)
        if comment is None:
            return False

        comment.is_deleted = True
        comment.content = "[삭제된 댓글입니다]"  # 내용 마스킹
        await self.session.flush()
        logger.debug(f"Soft deleted comment: {comment_id}")
        return True

    async def count_by_post(self, post_id: uuid.UUID) -> int:
        """
        게시글의 댓글 총 개수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 댓글 수
        """
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.post_id == post_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def count_replies(self, parent_id: uuid.UUID) -> int:
        """
        특정 댓글의 대댓글 수.

        Args:
            parent_id: 부모 댓글 UUID

        Returns:
            int: 대댓글 수
        """
        stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.parent_id == parent_id, Comment.is_deleted == False)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()
```

---

## 5. Service Layer

Service는 비즈니스 로직을 처리합니다.

### 5.1 Post Service (`app/api/v1/post/service.py`)

```python
"""
Post Service - Business logic for posts and comments.

Orchestrates operations between controller and repository layers.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.post.comment_repository import CommentRepository
from app.api.v1.post.repository import PostRepository
from app.models.comment import Comment
from app.models.post import Post

logger = logging.getLogger(__name__)


@dataclass
class CommentTreeNode:
    """
    댓글 트리 노드 DTO.

    계층 구조를 클라이언트에 전달하기 위한 형태.
    """
    id: uuid.UUID
    user_id: str
    user_name: str | None
    content: str
    depth: int
    created_at: str
    is_deleted: bool
    replies: list["CommentTreeNode"]

    @classmethod
    def from_comment(cls, comment: Comment) -> "CommentTreeNode":
        """Comment 엔티티를 트리 노드로 변환."""
        return cls(
            id=comment.id,
            user_id=comment.user_id,
            user_name=comment.user.name if comment.user else None,
            content=comment.content if not comment.is_deleted else "[삭제된 댓글입니다]",
            depth=comment.depth,
            created_at=comment.created_at.isoformat(),
            is_deleted=comment.is_deleted,
            replies=[],  # 나중에 채워짐
        )


class PostService:
    """
    Post 관련 비즈니스 로직을 처리하는 서비스.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.post_repo = PostRepository(session)
        self.comment_repo = CommentRepository(session)

    # ========================================
    # Post Methods
    # ========================================

    async def create_post(self, user_id: str, title: str, content: str) -> Post:
        """
        새 게시글 작성.

        Args:
            user_id: 작성자 ID
            title: 제목
            content: 내용

        Returns:
            생성된 Post
        """
        post = Post(
            user_id=user_id,
            title=title,
            content=content,
        )
        created = await self.post_repo.create(post)
        await self.session.commit()
        logger.info(f"Post created: {created.id} by user {user_id}")
        return created

    async def get_post(self, post_id: uuid.UUID) -> Post | None:
        """게시글 단건 조회."""
        return await self.post_repo.get_by_id(post_id)

    async def get_post_with_comments(self, post_id: uuid.UUID) -> Post | None:
        """게시글 + 댓글 조회."""
        return await self.post_repo.get_by_id_with_comments(post_id)

    async def list_posts(
        self,
        limit: int = 20,
        offset: int = 0,
        user_id: str | None = None,
    ) -> Sequence[Post]:
        """게시글 목록 조회."""
        return await self.post_repo.get_all(limit=limit, offset=offset, user_id=user_id)

    async def update_post(
        self,
        post_id: uuid.UUID,
        user_id: str,
        title: str | None = None,
        content: str | None = None,
    ) -> Post | None:
        """
        게시글 수정.

        Args:
            post_id: 게시글 UUID
            user_id: 요청한 사용자 ID (권한 확인용)
            title: 새 제목 (선택)
            content: 새 내용 (선택)

        Returns:
            수정된 Post 또는 None (권한 없음/존재하지 않음)
        """
        post = await self.post_repo.get_by_id(post_id)

        if post is None:
            return None

        # 권한 확인: 작성자만 수정 가능
        if post.user_id != user_id:
            logger.warning(f"User {user_id} tried to edit post {post_id} owned by {post.user_id}")
            return None

        if title is not None:
            post.title = title
        if content is not None:
            post.content = content

        updated = await self.post_repo.update(post)
        await self.session.commit()
        return updated

    async def delete_post(self, post_id: uuid.UUID, user_id: str) -> bool:
        """
        게시글 삭제.

        Args:
            post_id: 게시글 UUID
            user_id: 요청한 사용자 ID

        Returns:
            bool: 삭제 성공 여부
        """
        post = await self.post_repo.get_by_id(post_id)

        if post is None:
            return False

        if post.user_id != user_id:
            logger.warning(f"User {user_id} tried to delete post {post_id}")
            return False

        result = await self.post_repo.soft_delete(post_id)
        await self.session.commit()
        return result

    # ========================================
    # Comment Methods
    # ========================================

    async def create_comment(
        self,
        post_id: uuid.UUID,
        user_id: str,
        content: str,
        parent_id: uuid.UUID | None = None,
    ) -> Comment | None:
        """
        댓글/대댓글 작성.

        대댓글의 경우:
        - parent_id가 있으면 해당 댓글의 depth + 1
        - order_number는 부모의 것을 상속

        최상위 댓글의 경우:
        - depth = 0
        - order_number = 새로 할당

        Args:
            post_id: 게시글 UUID
            user_id: 작성자 ID
            content: 내용
            parent_id: 부모 댓글 UUID (대댓글인 경우)

        Returns:
            생성된 Comment 또는 None (게시글/부모 댓글이 없는 경우)
        """
        # 게시글 존재 확인
        post = await self.post_repo.get_by_id(post_id)
        if post is None:
            logger.warning(f"Post {post_id} not found for comment creation")
            return None

        depth = 0
        order_number = 0

        if parent_id is not None:
            # 대댓글: 부모 댓글 확인
            parent = await self.comment_repo.get_by_id(parent_id)
            if parent is None:
                logger.warning(f"Parent comment {parent_id} not found")
                return None

            # 부모 댓글이 같은 게시글에 속하는지 확인
            if parent.post_id != post_id:
                logger.warning(f"Parent comment {parent_id} belongs to different post")
                return None

            depth = parent.depth + 1
            order_number = parent.order_number  # 부모의 그룹에 속함
        else:
            # 최상위 댓글: 새 order_number 할당
            order_number = await self.comment_repo.get_next_order_number(post_id)

        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            parent_id=parent_id,
            content=content,
            depth=depth,
            order_number=order_number,
        )

        created = await self.comment_repo.create(comment)
        await self.session.commit()
        logger.info(
            f"Comment created: {created.id} on post {post_id}, "
            f"parent={parent_id}, depth={depth}"
        )
        return created

    async def get_comments_tree(self, post_id: uuid.UUID) -> list[CommentTreeNode]:
        """
        게시글의 댓글을 트리 구조로 조회.

        플랫 리스트를 트리 구조로 변환하여 반환합니다.

        Args:
            post_id: 게시글 ID

        Returns:
            list[CommentTreeNode]: 최상위 댓글 목록 (각각 replies 포함)
        """
        # 모든 댓글을 플랫하게 조회
        all_comments = await self.comment_repo.get_all_comments_by_post(
            post_id, include_deleted=True  # 삭제된 것도 구조 유지용으로 포함
        )

        # ID -> TreeNode 매핑
        node_map: dict[uuid.UUID, CommentTreeNode] = {}
        root_nodes: list[CommentTreeNode] = []

        # 1단계: 모든 노드 생성
        for comment in all_comments:
            node = CommentTreeNode.from_comment(comment)
            node_map[comment.id] = node

        # 2단계: 트리 구조 구축
        for comment in all_comments:
            node = node_map[comment.id]

            if comment.parent_id is None:
                # 최상위 댓글
                root_nodes.append(node)
            else:
                # 대댓글: 부모 노드에 추가
                parent_node = node_map.get(comment.parent_id)
                if parent_node:
                    parent_node.replies.append(node)

        return root_nodes

    async def get_flat_comments(
        self,
        post_id: uuid.UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Comment]:
        """
        게시글의 댓글을 플랫 리스트로 조회.

        depth와 order_number로 정렬되어 있어
        프론트엔드에서 들여쓰기로 표현 가능.

        Args:
            post_id: 게시글 ID
            limit: 최대 조회 수
            offset: 건너뛸 수

        Returns:
            Sequence[Comment]: 정렬된 댓글 리스트
        """
        return await self.comment_repo.get_all_comments_by_post(post_id)

    async def update_comment(
        self,
        comment_id: uuid.UUID,
        user_id: str,
        content: str,
    ) -> Comment | None:
        """
        댓글 수정.

        Args:
            comment_id: 댓글 UUID
            user_id: 요청 사용자 ID
            content: 새 내용

        Returns:
            수정된 Comment 또는 None
        """
        comment = await self.comment_repo.get_by_id(comment_id)

        if comment is None:
            return None

        if comment.user_id != user_id:
            logger.warning(f"User {user_id} tried to edit comment {comment_id}")
            return None

        comment.content = content
        updated = await self.comment_repo.update(comment)
        await self.session.commit()
        return updated

    async def delete_comment(self, comment_id: uuid.UUID, user_id: str) -> bool:
        """
        댓글 삭제 (소프트 삭제).

        대댓글이 있어도 구조는 유지됩니다.

        Args:
            comment_id: 댓글 UUID
            user_id: 요청 사용자 ID

        Returns:
            bool: 삭제 성공 여부
        """
        comment = await self.comment_repo.get_by_id(comment_id)

        if comment is None:
            return False

        if comment.user_id != user_id:
            logger.warning(f"User {user_id} tried to delete comment {comment_id}")
            return False

        result = await self.comment_repo.soft_delete(comment_id)
        await self.session.commit()
        return result

    async def get_reply_count(self, comment_id: uuid.UUID) -> int:
        """특정 댓글의 대댓글 수 조회."""
        return await self.comment_repo.count_replies(comment_id)

    async def get_comment_count(self, post_id: uuid.UUID) -> int:
        """게시글의 총 댓글 수 조회."""
        return await self.comment_repo.count_by_post(post_id)
```

---

## 6. Schemas (Pydantic)

API 요청/응답을 위한 Pydantic 스키마입니다.

### 6.1 Post Schemas (`app/api/v1/post/schemas.py`)

```python
"""
Pydantic schemas for Post and Comment API endpoints.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


# ========================================
# Post Schemas
# ========================================

class PostCreate(BaseModel):
    """게시글 생성 요청."""
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)


class PostUpdate(BaseModel):
    """게시글 수정 요청."""
    title: str | None = Field(None, min_length=1, max_length=200)
    content: str | None = Field(None, min_length=1)


class PostResponse(BaseModel):
    """게시글 응답."""
    id: uuid.UUID
    user_id: str
    user_name: str | None = None
    title: str
    content: str
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0

    class Config:
        from_attributes = True


class PostListResponse(BaseModel):
    """게시글 목록 응답."""
    items: list[PostResponse]
    total: int
    limit: int
    offset: int


# ========================================
# Comment Schemas
# ========================================

class CommentCreate(BaseModel):
    """댓글 생성 요청."""
    content: str = Field(..., min_length=1, max_length=1000)
    parent_id: uuid.UUID | None = Field(None, description="대댓글인 경우 부모 댓글 UUID")


class CommentUpdate(BaseModel):
    """댓글 수정 요청."""
    content: str = Field(..., min_length=1, max_length=1000)


class CommentResponse(BaseModel):
    """댓글 단일 응답."""
    id: uuid.UUID
    post_id: uuid.UUID
    user_id: str
    user_name: str | None = None
    parent_id: uuid.UUID | None
    content: str
    depth: int
    created_at: datetime
    updated_at: datetime
    is_deleted: bool = False
    reply_count: int = 0

    class Config:
        from_attributes = True


class CommentTreeResponse(BaseModel):
    """댓글 트리 노드 응답 (재귀 구조)."""
    id: uuid.UUID
    user_id: str
    user_name: str | None
    content: str
    depth: int
    created_at: str
    is_deleted: bool
    replies: list["CommentTreeResponse"] = []

    class Config:
        from_attributes = True


# Forward reference 해결
CommentTreeResponse.model_rebuild()


class CommentListResponse(BaseModel):
    """댓글 목록 응답 (플랫)."""
    items: list[CommentResponse]
    total: int


class CommentTreeListResponse(BaseModel):
    """댓글 트리 목록 응답."""
    items: list[CommentTreeResponse]
    total: int
```

---

## 7. API Endpoints

FastAPI 라우터 정의입니다.

### 7.1 Post Controller (`app/api/v1/post/controller.py`)

```python
"""
Post API endpoints.

게시글 및 댓글 CRUD API를 제공합니다.

Architecture Flow (기존 jwt_test 모듈과 동일):
1. Request hits this controller (routes)
2. JWT Guard validates the token (interpreter/jwt_guard.py)
3. Controller calls Service layer (service.py)
4. Service calls Repository layer (repository.py, comment_repository.py)
5. Repository queries Database
6. Response flows back up the chain
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.interpreter import CurrentUser, JWTPayload
from app.api.v1.post.schemas import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentTreeListResponse,
    CommentTreeResponse,
    CommentUpdate,
    PostCreate,
    PostListResponse,
    PostResponse,
    PostUpdate,
)
from app.api.v1.post.service import CommentTreeNode, PostService
from app.core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/posts", tags=["posts"])


# ========================================
# Dependencies
# ========================================

async def get_post_service(
    session: AsyncSession = Depends(get_db),
) -> PostService:
    """PostService 의존성 주입."""
    return PostService(session)


# Type alias for service dependency
Service = Annotated[PostService, Depends(get_post_service)]

# Note: CurrentUser는 app.api.v1.interpreter에서 이미 정의되어 있음
# CurrentUser = Annotated[JWTPayload, Depends(get_current_user)]


# ========================================
# Post Endpoints
# ========================================

@router.post(
    "",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="게시글 작성",
)
async def create_post(
    data: PostCreate,
    current_user: CurrentUser,
    service: Service,
) -> PostResponse:
    """
    새 게시글을 작성합니다.

    - **title**: 게시글 제목 (1-200자)
    - **content**: 게시글 내용
    """
    post = await service.create_post(
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        comment_count=0,
    )


@router.get(
    "",
    response_model=PostListResponse,
    summary="게시글 목록 조회",
)
async def list_posts(
    service: Service,
    limit: int = 20,
    offset: int = 0,
    user_id: str | None = None,
) -> PostListResponse:
    """
    게시글 목록을 조회합니다.

    - **limit**: 최대 조회 수 (기본 20)
    - **offset**: 건너뛸 수 (기본 0)
    - **user_id**: 특정 사용자의 글만 조회 (선택)
    """
    posts = await service.list_posts(limit=limit, offset=offset, user_id=user_id)
    total = await service.post_repo.count(user_id=user_id)

    items = []
    for post in posts:
        comment_count = await service.get_comment_count(post.id)
        items.append(
            PostResponse(
                id=post.id,
                user_id=post.user_id,
                user_name=post.user.name if post.user else None,
                title=post.title,
                content=post.content,
                created_at=post.created_at,
                updated_at=post.updated_at,
                comment_count=comment_count,
            )
        )

    return PostListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 상세 조회",
)
async def get_post(
    post_id: uuid.UUID,
    service: Service,
) -> PostResponse:
    """게시글 상세 정보를 조회합니다."""
    post = await service.get_post(post_id)

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )

    comment_count = await service.get_comment_count(post_id)

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        user_name=post.user.name if post.user else None,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
        comment_count=comment_count,
    )


@router.patch(
    "/{post_id}",
    response_model=PostResponse,
    summary="게시글 수정",
)
async def update_post(
    post_id: uuid.UUID,
    data: PostUpdate,
    current_user: CurrentUser,
    service: Service,
) -> PostResponse:
    """
    게시글을 수정합니다.

    작성자만 수정 가능합니다.
    """
    post = await service.update_post(
        post_id=post_id,
        user_id=current_user.user_id,
        title=data.title,
        content=data.content,
    )

    if post is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or no permission",
        )

    return PostResponse(
        id=post.id,
        user_id=post.user_id,
        title=post.title,
        content=post.content,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="게시글 삭제",
)
async def delete_post(
    post_id: uuid.UUID,
    current_user: CurrentUser,
    service: Service,
) -> None:
    """
    게시글을 삭제합니다.

    작성자만 삭제 가능합니다.
    """
    result = await service.delete_post(
        post_id=post_id,
        user_id=current_user.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found or no permission",
        )


# ========================================
# Comment Endpoints
# ========================================

@router.post(
    "/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="댓글/대댓글 작성",
)
async def create_comment(
    post_id: uuid.UUID,
    data: CommentCreate,
    current_user: CurrentUser,
    service: Service,
) -> CommentResponse:
    """
    댓글 또는 대댓글을 작성합니다.

    - **content**: 댓글 내용 (1-1000자)
    - **parent_id**: 대댓글인 경우 부모 댓글 ID (선택)
    """
    comment = await service.create_comment(
        post_id=post_id,
        user_id=current_user.user_id,
        content=data.content,
        parent_id=data.parent_id,
    )

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post or parent comment not found",
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        depth=comment.depth,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.get(
    "/{post_id}/comments",
    response_model=CommentListResponse,
    summary="댓글 목록 조회 (플랫)",
)
async def list_comments_flat(
    post_id: uuid.UUID,
    service: Service,
) -> CommentListResponse:
    """
    게시글의 댓글을 플랫 리스트로 조회합니다.

    depth와 order_number로 정렬되어 있어
    프론트엔드에서 depth 값으로 들여쓰기 표현이 가능합니다.
    """
    comments = await service.get_flat_comments(post_id)
    total = await service.get_comment_count(post_id)

    items = []
    for comment in comments:
        reply_count = await service.get_reply_count(comment.id)
        items.append(
            CommentResponse(
                id=comment.id,
                post_id=comment.post_id,
                user_id=comment.user_id,
                user_name=comment.user.name if comment.user else None,
                parent_id=comment.parent_id,
                content=comment.content,
                depth=comment.depth,
                created_at=comment.created_at,
                updated_at=comment.updated_at,
                is_deleted=comment.is_deleted,
                reply_count=reply_count,
            )
        )

    return CommentListResponse(items=items, total=total)


@router.get(
    "/{post_id}/comments/tree",
    response_model=CommentTreeListResponse,
    summary="댓글 목록 조회 (트리)",
)
async def list_comments_tree(
    post_id: uuid.UUID,
    service: Service,
) -> CommentTreeListResponse:
    """
    게시글의 댓글을 트리 구조로 조회합니다.

    각 댓글의 replies 필드에 대댓글이 재귀적으로 포함됩니다.
    """
    tree = await service.get_comments_tree(post_id)
    total = await service.get_comment_count(post_id)

    def convert_node(node: CommentTreeNode) -> CommentTreeResponse:
        return CommentTreeResponse(
            id=node.id,
            user_id=node.user_id,
            user_name=node.user_name,
            content=node.content,
            depth=node.depth,
            created_at=node.created_at,
            is_deleted=node.is_deleted,
            replies=[convert_node(r) for r in node.replies],
        )

    items = [convert_node(node) for node in tree]

    return CommentTreeListResponse(items=items, total=total)


@router.patch(
    "/{post_id}/comments/{comment_id}",
    response_model=CommentResponse,
    summary="댓글 수정",
)
async def update_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    data: CommentUpdate,
    current_user: CurrentUser,
    service: Service,
) -> CommentResponse:
    """
    댓글을 수정합니다.

    작성자만 수정 가능합니다.
    """
    comment = await service.update_comment(
        comment_id=comment_id,
        user_id=current_user.user_id,
        content=data.content,
    )

    if comment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or no permission",
        )

    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        user_id=comment.user_id,
        parent_id=comment.parent_id,
        content=comment.content,
        depth=comment.depth,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.delete(
    "/{post_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="댓글 삭제",
)
async def delete_comment(
    post_id: uuid.UUID,
    comment_id: uuid.UUID,
    current_user: CurrentUser,
    service: Service,
) -> None:
    """
    댓글을 삭제합니다.

    대댓글이 있는 경우 내용만 마스킹되고 구조는 유지됩니다.
    작성자만 삭제 가능합니다.
    """
    result = await service.delete_comment(
        comment_id=comment_id,
        user_id=current_user.user_id,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found or no permission",
        )
```

### 7.2 모듈 `__init__.py` (`app/api/v1/post/__init__.py`)

NestJS-like 모듈 구조를 따라 `__init__.py`에서 router를 export합니다:

```python
"""
Post Module - Bulletin board with nested comments feature module.

This module follows a NestJS-like structure where all related components
(controller, service, repository, schemas) are grouped together.

Structure:
- controller.py       : API route handlers (like NestJS controllers)
- service.py          : Business logic layer (like NestJS services)
- repository.py       : Post data access layer
- comment_repository.py : Comment data access layer
- schemas.py          : Pydantic schemas for request/response validation
"""

from app.api.v1.post.controller import router

__all__ = ["router"]
```

### 7.3 라우터 등록

`app/api/v1/router.py`에 추가:

```python
"""
API v1 router - combines all endpoint routers.
"""

from fastapi import APIRouter

from app.api.v1.routes.agent import router as agent_router
from app.api.v1.routes.feeds import router as feeds_router
from app.api.v1.jwt_test import router as jwt_test_router
from app.api.v1.post import router as post_router  # 추가

api_router = APIRouter()

# Include all routers
api_router.include_router(feeds_router, prefix="/feeds", tags=["feeds"])
api_router.include_router(agent_router, prefix="/agent", tags=["agent"])
api_router.include_router(jwt_test_router, prefix="/jwt-test", tags=["jwt-test", "auth"])
api_router.include_router(post_router)  # 추가 (prefix는 controller에서 이미 정의됨)
```

---

## 8. 사용 예시

### 8.1 게시글 작성

```bash
POST /api/v1/posts
Authorization: Bearer <token>

{
  "title": "첫 번째 게시글",
  "content": "안녕하세요! 첫 게시글입니다."
}
```

### 8.2 댓글 작성 (최상위)

```bash
POST /api/v1/posts/550e8400-e29b-41d4-a716-446655440000/comments
Authorization: Bearer <token>

{
  "content": "좋은 글이네요!"
}
```

### 8.3 대댓글 작성

```bash
POST /api/v1/posts/550e8400-e29b-41d4-a716-446655440000/comments
Authorization: Bearer <token>

{
  "content": "저도 동의합니다!",
  "parent_id": "550e8400-e29b-41d4-a716-446655440001"  # 부모 댓글 UUID
}
```

### 8.4 댓글 트리 조회 응답 예시

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "user_id": "user123",
      "user_name": "홍길동",
      "content": "좋은 글이네요!",
      "depth": 0,
      "created_at": "2024-01-15T10:00:00Z",
      "is_deleted": false,
      "replies": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440002",
          "user_id": "user456",
          "user_name": "김철수",
          "content": "저도 동의합니다!",
          "depth": 1,
          "created_at": "2024-01-15T10:05:00Z",
          "is_deleted": false,
          "replies": [
            {
              "id": "550e8400-e29b-41d4-a716-446655440003",
              "user_id": "user123",
              "user_name": "홍길동",
              "content": "감사합니다 ㅎㅎ",
              "depth": 2,
              "created_at": "2024-01-15T10:10:00Z",
              "is_deleted": false,
              "replies": []
            }
          ]
        }
      ]
    }
  ],
  "total": 3
}
```

---

## 디렉토리 구조 요약

현재 서버의 NestJS-like 모듈 구조를 따릅니다:

```
app/
├── api/
│   └── v1/
│       ├── interpreter/          # JWT 인증 가드 (기존)
│       │   ├── __init__.py       # CurrentUser, JWTPayload 등 export
│       │   └── jwt_guard.py      # JWT 검증 로직
│       ├── jwt_test/             # 사용자 인증 모듈 (기존, 참고용)
│       │   ├── __init__.py
│       │   ├── controller.py
│       │   ├── service.py
│       │   ├── repository.py
│       │   └── schemas.py
│       ├── post/                 # 게시판 모듈 (신규)
│       │   ├── __init__.py       # router export
│       │   ├── controller.py     # API 엔드포인트
│       │   ├── service.py        # 비즈니스 로직
│       │   ├── repository.py     # Post 데이터 접근
│       │   ├── comment_repository.py  # Comment 데이터 접근
│       │   └── schemas.py        # Pydantic 스키마
│       └── router.py             # 모든 라우터 통합
├── models/
│   ├── __init__.py               # 모든 모델 export
│   ├── user.py                   # User 엔티티 (기존, 관계 추가)
│   ├── post.py                   # Post 엔티티 (신규)
│   └── comment.py                # Comment 엔티티 (신규, Self-Join)
└── core/
    ├── config.py                 # 설정 (기존)
    └── database.py               # DB 설정 (기존)
```

### 기존 구조와의 일관성

이 구현은 기존 `jwt_test` 모듈의 구조를 따릅니다:
- **controller.py**: API 라우트 핸들러 (NestJS Controller와 유사)
- **service.py**: 비즈니스 로직 레이어 (NestJS Service와 유사)
- **repository.py**: 데이터 접근 레이어 (NestJS Repository와 유사)
- **schemas.py**: 요청/응답 검증용 Pydantic 스키마
- **`__init__.py`**: 모듈에서 router를 export

---

## 9. 코드 간 상호작용 및 데이터 흐름 상세 설명

이 섹션에서는 각 레이어의 코드가 어떻게 서로 연결되고, 데이터가 어떻게 흘러가는지 상세히 설명합니다.

---

### 9.1 전체 아키텍처 흐름

```
HTTP Request
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Controller (controller.py)                                      │
│  - HTTP 요청 수신                                                │
│  - CurrentUser 의존성으로 JWT 검증                               │
│  - Pydantic Schema로 요청 데이터 검증                            │
│  - Service 호출                                                  │
│  - 응답 Schema로 변환하여 반환                                   │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Service (service.py)                                            │
│  - 비즈니스 로직 처리                                            │
│  - 여러 Repository 조합                                          │
│  - 트랜잭션 관리 (commit/rollback)                               │
│  - 권한 검증                                                     │
│  - 데이터 변환 (Entity → DTO)                                    │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Repository (repository.py, comment_repository.py)               │
│  - 순수 데이터베이스 작업                                        │
│  - SQLAlchemy 쿼리 실행                                          │
│  - Entity 반환                                                   │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  Model/Entity (post.py, comment.py)                              │
│  - 테이블 스키마 정의                                            │
│  - 관계(Relationship) 정의                                       │
│  - 데이터베이스와 1:1 매핑                                       │
└─────────────────────────────────────────────────────────────────┘
     │
     ▼
  Database (PostgreSQL)
```

---

### 9.2 Model 컬럼 정의 상세 설명

#### Post 모델 컬럼별 상세 분석

```python
class Post(Base):
    __tablename__ = "posts"  # 실제 DB 테이블 이름
```

| 코드 | 설명 |
|------|------|
| `__tablename__ = "posts"` | PostgreSQL에 `posts`라는 이름의 테이블 생성 |

---

```python
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `id: Mapped[uuid.UUID]` | Python 타입 힌트. SQLAlchemy가 이 컬럼이 UUID 타입임을 인식 | - |
| `UUID(as_uuid=True)` | PostgreSQL의 `UUID` 타입 사용. `as_uuid=True`는 Python uuid 객체로 자동 변환 | `id UUID` |
| `primary_key=True` | 이 컬럼을 테이블의 기본 키로 설정 | `PRIMARY KEY` 제약조건 |
| `default=uuid.uuid4` | INSERT 시 값이 없으면 Python에서 UUID v4 자동 생성 | (DB 기본값 아님, ORM 레벨) |

**생성되는 SQL:**
```sql
CREATE TABLE posts (
    id UUID PRIMARY KEY,
    ...
);
```

---

```python
    user_id: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `user_id: Mapped[str]` | Python에서 문자열로 취급 | - |
| `String(25)` | 최대 25자 VARCHAR | `VARCHAR(25)` |
| `ForeignKey("users.id", ...)` | `users` 테이블의 `id` 컬럼 참조 | `REFERENCES users(id)` |
| `ondelete="CASCADE"` | 참조된 User 삭제 시 이 Post도 자동 삭제 | `ON DELETE CASCADE` |
| `nullable=False` | NULL 값 허용 안 함 | `NOT NULL` |
| `index=True` | 이 컬럼에 인덱스 생성 (조회 성능 향상) | `CREATE INDEX ...` |

**생성되는 SQL:**
```sql
CREATE TABLE posts (
    ...
    user_id VARCHAR(25) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ...
);
CREATE INDEX ix_posts_user_id ON posts(user_id);
```

---

```python
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `String(200)` | 최대 200자 제한 (제목용) | `VARCHAR(200)` |
| `Text` | 길이 제한 없는 텍스트 (본문용) | `TEXT` |
| `nullable=False` | 필수 입력 필드 | `NOT NULL` |

**생성되는 SQL:**
```sql
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
```

---

```python
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `Mapped[datetime]` | Python datetime 객체로 매핑 | - |
| `DateTime(timezone=True)` | 타임존 정보 포함 | `TIMESTAMP WITH TIME ZONE` |
| `server_default=func.now()` | **DB 서버**에서 현재 시간 자동 설정 | `DEFAULT NOW()` |
| `nullable=False` | NULL 불가 | `NOT NULL` |

**`default` vs `server_default` 차이:**
```python
# default=func.now()  → Python ORM에서 시간 생성 (INSERT SQL에 값 포함)
# server_default=func.now()  → DB 서버가 시간 생성 (INSERT SQL에 값 없음)
```

**생성되는 SQL:**
```sql
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
```

---

```python
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `onupdate=func.now()` | UPDATE 쿼리 실행 시 자동으로 현재 시간 갱신 | (ORM 레벨, 트리거 아님) |

**주의:** `onupdate`는 SQLAlchemy ORM 레벨에서 동작합니다. 직접 SQL로 UPDATE하면 갱신 안 됨.

---

```python
    is_deleted: Mapped[bool] = mapped_column(default=False, nullable=False)
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `Mapped[bool]` | Python boolean | `BOOLEAN` |
| `default=False` | ORM에서 INSERT 시 기본값 False | (ORM 레벨) |
| `nullable=False` | NULL 불가 | `NOT NULL` |

---

#### Comment 모델 컬럼별 상세 분석

```python
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```
→ Post와 동일. 각 댓글의 고유 식별자.

---

```python
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `UUID(as_uuid=True)` | Post의 id와 같은 UUID 타입 | `UUID` |
| `ForeignKey("posts.id", ...)` | `posts.id`를 참조하는 외래 키 | `REFERENCES posts(id)` |
| `ondelete="CASCADE"` | 게시글 삭제 시 모든 댓글도 삭제 | `ON DELETE CASCADE` |
| `index=True` | 게시글별 댓글 조회 성능 향상 | 인덱스 생성 |

**왜 index가 중요한가:**
```python
# 이 쿼리가 자주 실행됨
SELECT * FROM comments WHERE post_id = 'uuid-xxx';
# index=True가 없으면 전체 테이블 스캔 (느림)
# index=True가 있으면 인덱스 스캔 (빠름)
```

---

```python
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),
        nullable=True,  # ← 핵심!
        index=True,
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `Mapped[Optional[uuid.UUID]]` | Python에서 `None` 가능 | - |
| `ForeignKey("comments.id", ...)` | **자기 자신 테이블** 참조 (Self-Join) | `REFERENCES comments(id)` |
| `nullable=True` | **NULL 허용** = 최상위 댓글 | `NULL 허용` |
| `ondelete="CASCADE"` | 부모 댓글 삭제 시 대댓글도 삭제 | `ON DELETE CASCADE` |

**Self-Join의 핵심:**
```sql
-- parent_id가 NULL이면 최상위 댓글
INSERT INTO comments (id, post_id, parent_id, ...)
VALUES ('uuid-1', 'post-uuid', NULL, ...);  -- 최상위 댓글

-- parent_id가 있으면 대댓글
INSERT INTO comments (id, post_id, parent_id, ...)
VALUES ('uuid-2', 'post-uuid', 'uuid-1', ...);  -- uuid-1의 대댓글
```

---

```python
    depth: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="댓글 깊이: 0=최상위, 1=대댓글, 2=대대댓글...",
    )
```

| 코드 부분 | 역할 | DB 영향 |
|-----------|------|---------|
| `Integer` | 정수 타입 | `INTEGER` |
| `default=0` | 기본값 0 (최상위 댓글) | (ORM 레벨) |
| `comment="..."` | DB 컬럼에 주석 추가 (문서화용) | `COMMENT ON COLUMN ...` |

**depth 값 예시:**
```
depth=0: 최상위 댓글
depth=1: 대댓글 (1단계 중첩)
depth=2: 대대댓글 (2단계 중첩)
depth=N: N단계 중첩
```

---

```python
    order_number: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="같은 그룹 내 정렬 순서",
    )
```

| 코드 부분 | 역할 |
|-----------|------|
| `order_number` | 같은 "댓글 스레드"를 그룹핑하는 번호 |

**order_number 동작 방식:**
```
최상위 댓글 A → order_number = 1 (새로 할당)
  └─ 대댓글 A-1 → order_number = 1 (부모에서 상속)
     └─ 대대댓글 A-1-1 → order_number = 1 (부모에서 상속)

최상위 댓글 B → order_number = 2 (새로 할당)
  └─ 대댓글 B-1 → order_number = 2 (부모에서 상속)
```

---

#### Relationship 정의 상세 분석

```python
    # Post 모델에서
    user: Mapped["User"] = relationship("User", back_populates="posts")
```

| 코드 부분 | 역할 |
|-----------|------|
| `Mapped["User"]` | 이 필드가 User 객체를 참조함을 명시 |
| `relationship("User", ...)` | SQLAlchemy에게 User 모델과 관계 있음을 알림 |
| `back_populates="posts"` | User 모델의 `posts` 필드와 양방향 연결 |

**양방향 관계 동작:**
```python
# post.user로 작성자 접근
post = await session.get(Post, post_id)
print(post.user.name)  # "홍길동"

# user.posts로 작성한 글 목록 접근
user = await session.get(User, user_id)
print(len(user.posts))  # 5 (작성한 글 5개)
```

---

```python
    # Comment 모델에서 - Self-Join 관계
    parent: Mapped[Optional["Comment"]] = relationship(
        "Comment",
        remote_side=[id],
        back_populates="replies",
        foreign_keys=[parent_id],
    )
```

| 코드 부분 | 역할 |
|-----------|------|
| `Mapped[Optional["Comment"]]` | 부모 댓글이 없을 수 있음 (최상위 댓글) |
| `remote_side=[id]` | Self-Join에서 "1" 쪽이 `id`임을 명시 |
| `back_populates="replies"` | `replies` 필드와 양방향 연결 |
| `foreign_keys=[parent_id]` | 이 관계가 `parent_id` FK를 사용함을 명시 |

**`remote_side` 설명:**
```
Comment A (id=1) ←─── Comment B (parent_id=1)
          │                    │
     remote_side          foreign_keys
     (관계의 "1" 쪽)      (관계의 "N" 쪽)
```

---

```python
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",
        foreign_keys=[parent_id],
    )
```

| 코드 부분 | 역할 |
|-----------|------|
| `Mapped[list["Comment"]]` | 여러 대댓글을 리스트로 가짐 |
| `cascade="all, delete-orphan"` | 부모 삭제 시 자식도 삭제, 연결 끊기면 삭제 |
| `foreign_keys=[parent_id]` | `parent_id`로 연결된 댓글들을 찾음 |

**cascade 옵션 상세:**
```python
cascade="all, delete-orphan"

# "all" 포함 내용:
# - save-update: 부모 저장 시 자식도 저장
# - merge: 부모 병합 시 자식도 병합
# - delete: 부모 삭제 시 자식도 삭제
# - refresh-expire: 부모 새로고침 시 자식도 새로고침

# "delete-orphan" 추가:
# - 자식이 부모와의 연결이 끊기면 자동 삭제
# - 예: comment.replies.remove(child_comment) → child_comment 삭제됨
```

---

### 9.3 Model 간 상호작용 상세

#### Comment의 Self-Join 관계가 동작하는 방식

```python
# comment.py에서 정의된 Self-Join 관계

class Comment(Base):
    # 1. 자기 자신의 Primary Key
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)

    # 2. 부모 댓글을 가리키는 Foreign Key (자기 자신 테이블 참조)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("comments.id", ondelete="CASCADE"),  # ← 자기 테이블의 id 참조
        nullable=True,  # NULL이면 최상위 댓글
    )

    # 3. 부모 댓글 관계 (N:1 - 여러 대댓글이 하나의 부모를 가짐)
    parent: Mapped[Optional["Comment"]] = relationship(
        "Comment",
        remote_side=[id],  # ← "id"가 관계의 "1" 쪽임을 명시
        back_populates="replies",
        foreign_keys=[parent_id],
    )

    # 4. 자식 댓글들 관계 (1:N - 하나의 댓글이 여러 대댓글을 가짐)
    replies: Mapped[list["Comment"]] = relationship(
        "Comment",
        back_populates="parent",
        cascade="all, delete-orphan",  # ← 부모 삭제 시 자식도 삭제
        foreign_keys=[parent_id],
    )
```

**상호작용 설명:**

```
Comment A (id=uuid1, parent_id=NULL, depth=0)  ← 최상위 댓글
    │
    │  A.replies = [B, C]  (SQLAlchemy가 자동으로 로드)
    │
    ├── Comment B (id=uuid2, parent_id=uuid1, depth=1)
    │       │
    │       │  B.parent = A  (역참조)
    │       │  B.replies = [D]
    │       │
    │       └── Comment D (id=uuid4, parent_id=uuid2, depth=2)
    │               D.parent = B
    │
    └── Comment C (id=uuid3, parent_id=uuid1, depth=1)
            C.parent = A
            C.replies = []
```

#### 관계가 쿼리에 미치는 영향

```python
# Repository에서 selectinload 사용 시 발생하는 쿼리

# 1. get_top_level_comments 호출 시
stmt = select(Comment).options(
    selectinload(Comment.user),      # JOIN으로 user 정보 가져옴
    selectinload(Comment.replies),   # 별도 쿼리로 대댓글 가져옴
)

# 실제 발생하는 SQL:
# Query 1: SELECT * FROM comments WHERE post_id = ? AND parent_id IS NULL
# Query 2: SELECT * FROM users WHERE id IN (?, ?, ...)  -- 댓글 작성자들
# Query 3: SELECT * FROM comments WHERE parent_id IN (?, ?, ...)  -- 대댓글들
```

---

### 9.3 Controller → Service → Repository 데이터 흐름

#### 대댓글 작성 시나리오 상세 분석

```python
# ============================================================
# 1단계: Controller - HTTP 요청 수신 및 검증
# ============================================================

@router.post("/{post_id}/comments")
async def create_comment(
    post_id: uuid.UUID,           # ← URL에서 추출, FastAPI가 자동으로 UUID로 변환
    data: CommentCreate,          # ← Request Body를 Pydantic이 검증
    current_user: CurrentUser,    # ← JWT Guard가 토큰 검증 후 주입
    service: Service,             # ← Depends()로 PostService 인스턴스 주입
) -> CommentResponse:

    # Service 호출 - 모든 검증된 데이터 전달
    comment = await service.create_comment(
        post_id=post_id,
        user_id=current_user.user_id,  # JWT에서 추출된 사용자 ID
        content=data.content,
        parent_id=data.parent_id,       # 대댓글이면 부모 ID, 아니면 None
    )

    # Service가 None 반환 시 = 게시글 또는 부모 댓글이 없음
    if comment is None:
        raise HTTPException(status_code=404, detail="Post or parent comment not found")

    # Entity → Response Schema 변환
    return CommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        # ... 나머지 필드들
    )
```

```python
# ============================================================
# 2단계: Service - 비즈니스 로직 처리
# ============================================================

async def create_comment(
    self,
    post_id: uuid.UUID,
    user_id: str,
    content: str,
    parent_id: uuid.UUID | None = None,
) -> Comment | None:

    # 2-1. 게시글 존재 확인 (Repository 호출)
    post = await self.post_repo.get_by_id(post_id)
    if post is None:
        return None  # ← Controller에서 404로 변환됨

    # 2-2. depth와 order_number 계산 로직
    depth = 0
    order_number = 0

    if parent_id is not None:
        # 대댓글인 경우: 부모 댓글 확인
        parent = await self.comment_repo.get_by_id(parent_id)
        if parent is None:
            return None

        # 부모가 같은 게시글에 속하는지 검증
        if parent.post_id != post_id:
            return None

        # 부모의 depth + 1 = 자식의 depth
        depth = parent.depth + 1
        # 부모의 order_number 상속 (같은 그룹에 속함)
        order_number = parent.order_number
    else:
        # 최상위 댓글인 경우: 새로운 order_number 할당
        order_number = await self.comment_repo.get_next_order_number(post_id)

    # 2-3. Entity 생성
    comment = Comment(
        post_id=post_id,
        user_id=user_id,
        parent_id=parent_id,
        content=content,
        depth=depth,
        order_number=order_number,
    )

    # 2-4. Repository를 통해 DB에 저장
    created = await self.comment_repo.create(comment)

    # 2-5. 트랜잭션 커밋
    await self.session.commit()

    return created
```

```python
# ============================================================
# 3단계: Repository - 데이터베이스 작업
# ============================================================

async def create(self, comment: Comment) -> Comment:
    # 3-1. Session에 Entity 추가 (INSERT 예약)
    self.session.add(comment)

    # 3-2. flush로 DB에 INSERT 실행 (UUID 생성됨)
    await self.session.flush()

    # 3-3. DB에서 생성된 값 다시 로드 (created_at 등 서버 기본값)
    await self.session.refresh(comment)

    return comment

async def get_next_order_number(self, post_id: uuid.UUID) -> int:
    # 해당 게시글의 최대 order_number + 1 반환
    stmt = select(func.coalesce(func.max(Comment.order_number), 0)).where(
        Comment.post_id == post_id
    )
    result = await self.session.execute(stmt)
    return result.scalar_one() + 1
```

---

### 9.4 depth와 order_number의 역할

```
게시글 (post_id = "abc-123")
│
├── 댓글 A (depth=0, order_number=1) ← 첫 번째 최상위 댓글
│   ├── 대댓글 A-1 (depth=1, order_number=1) ← A의 order_number 상속
│   │   └── 대대댓글 A-1-1 (depth=2, order_number=1)
│   └── 대댓글 A-2 (depth=1, order_number=1)
│
├── 댓글 B (depth=0, order_number=2) ← 두 번째 최상위 댓글
│   └── 대댓글 B-1 (depth=1, order_number=2) ← B의 order_number 상속
│
└── 댓글 C (depth=0, order_number=3) ← 세 번째 최상위 댓글
```

**정렬 쿼리:**
```python
# order_number로 그룹핑, depth로 계층, created_at으로 시간순
.order_by(
    Comment.order_number.asc(),  # 같은 그룹끼리 모음
    Comment.depth.asc(),         # 부모가 자식보다 먼저
    Comment.created_at.asc(),    # 같은 레벨에서는 시간순
)
```

**결과 순서:**
```
A (order=1, depth=0)
A-1 (order=1, depth=1)
A-1-1 (order=1, depth=2)
A-2 (order=1, depth=1)
B (order=2, depth=0)
B-1 (order=2, depth=1)
C (order=3, depth=0)
```

---

### 9.5 트리 구조 변환 로직 상세

```python
async def get_comments_tree(self, post_id: uuid.UUID) -> list[CommentTreeNode]:
    # 1단계: DB에서 플랫 리스트로 모든 댓글 조회
    all_comments = await self.comment_repo.get_all_comments_by_post(post_id)

    # 결과: [A, A-1, A-1-1, A-2, B, B-1, C] (플랫 리스트)

    # 2단계: ID → Node 매핑 테이블 생성
    node_map: dict[uuid.UUID, CommentTreeNode] = {}
    root_nodes: list[CommentTreeNode] = []

    for comment in all_comments:
        node = CommentTreeNode.from_comment(comment)
        node_map[comment.id] = node

    # node_map = {
    #   "uuid-A": NodeA,
    #   "uuid-A-1": NodeA1,
    #   "uuid-A-1-1": NodeA11,
    #   ...
    # }

    # 3단계: 부모-자식 관계 연결
    for comment in all_comments:
        node = node_map[comment.id]

        if comment.parent_id is None:
            # 최상위 댓글 → root_nodes에 추가
            root_nodes.append(node)
        else:
            # 대댓글 → 부모 노드의 replies에 추가
            parent_node = node_map.get(comment.parent_id)
            if parent_node:
                parent_node.replies.append(node)

    # 최종 결과:
    # root_nodes = [
    #   NodeA { replies: [NodeA1 { replies: [NodeA11] }, NodeA2] },
    #   NodeB { replies: [NodeB1] },
    #   NodeC { replies: [] }
    # ]

    return root_nodes
```

---

### 9.6 의존성 주입 체인

```python
# Controller에서 의존성이 주입되는 순서

@router.post("/{post_id}/comments")
async def create_comment(
    post_id: uuid.UUID,
    data: CommentCreate,
    current_user: CurrentUser,  # ← 1번째로 실행
    service: Service,           # ← 2번째로 실행
):
```

**실행 순서:**

```
1. CurrentUser 의존성 (interpreter/jwt_guard.py)
   │
   ├── get_token_from_header() 실행
   │   └── Authorization 헤더에서 Bearer 토큰 추출
   │
   ├── get_token_from_cookie() 실행
   │   └── 쿠키에서 NextAuth 세션 토큰 추출
   │
   ├── decode_jwe_token() 실행
   │   └── AUTH_SECRET으로 JWE 토큰 복호화
   │
   └── JWTPayload.from_dict() 실행
       └── 토큰 데이터를 JWTPayload 객체로 변환

2. Service 의존성 (controller.py)
   │
   ├── get_db() 실행 (database.py)
   │   └── AsyncSessionLocal()로 DB 세션 생성
   │
   └── get_post_service() 실행
       └── PostService(session) 인스턴스 생성
           ├── self.post_repo = PostRepository(session)
           └── self.comment_repo = CommentRepository(session)

3. 모든 의존성 준비 완료 → create_comment 함수 실행
```

---

### 9.7 Soft Delete가 대댓글 구조에 미치는 영향

```python
# 소프트 삭제 시나리오

# 상황: A 댓글에 A-1 대댓글이 있는 상태에서 A 삭제 요청

async def soft_delete(self, comment_id: uuid.UUID) -> bool:
    comment = await self.get_by_id(comment_id)

    # is_deleted = True로 설정 (실제 삭제 X)
    comment.is_deleted = True

    # 내용을 마스킹 (개인정보 보호)
    comment.content = "[삭제된 댓글입니다]"

    await self.session.flush()
    return True
```

**결과:**
```
게시글
├── 댓글 A (is_deleted=True, content="[삭제된 댓글입니다]")
│   └── 대댓글 A-1 (is_deleted=False, content="원본 내용")  ← 구조 유지!
```

**트리 조회 시:**
```python
# include_deleted=True로 조회하면 삭제된 댓글도 포함
all_comments = await self.comment_repo.get_all_comments_by_post(
    post_id,
    include_deleted=True  # ← 구조 유지를 위해 삭제된 것도 포함
)
```

---

### 9.8 Cascade 삭제 동작

```python
# Model에서 정의된 cascade 설정

# Post → Comment 관계
comments: Mapped[list["Comment"]] = relationship(
    "Comment",
    cascade="all, delete-orphan",  # ← Post 삭제 시 모든 Comment 삭제
)

# Comment → Comment (Self-Join) 관계
replies: Mapped[list["Comment"]] = relationship(
    "Comment",
    cascade="all, delete-orphan",  # ← 부모 Comment 삭제 시 자식도 삭제
)

# ForeignKey에서 정의된 ondelete
ForeignKey("posts.id", ondelete="CASCADE")  # ← DB 레벨 cascade
```

**Hard Delete 시나리오 (실제 삭제):**
```
Post 삭제 요청
     │
     ▼
SQLAlchemy ORM cascade="all, delete-orphan"
     │
     ├── 모든 Comment 삭제 시작
     │   ├── Comment A 삭제
     │   │   └── A의 replies cascade → A-1, A-1-1, A-2 삭제
     │   ├── Comment B 삭제
     │   │   └── B의 replies cascade → B-1 삭제
     │   └── Comment C 삭제
     │
     ▼
Post 삭제 완료
```

---

## 핵심 포인트 정리

1. **Self-Join 패턴**: Comment가 자신을 참조하여 무한 대댓글 구현
2. **Soft Delete**: 대댓글이 있는 댓글도 구조 유지
3. **depth/order_number**: 계층 구조와 정렬 관리
4. **트리 변환**: Service에서 플랫 데이터를 트리로 변환
5. **Eager Loading**: N+1 문제 방지를 위한 selectinload 사용
