# Community Channel Implementation

This document describes the implementation plan for community channels (similar to Reddit subreddits or Blind channels) where users can group posts by topics and interests.

---

## Table of Contents

1. [Overview](#overview)
2. [Reference Platforms](#reference-platforms)
3. [Data Model Design](#data-model-design)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Business Logic](#business-logic)
7. [Error Handling](#error-handling)
8. [Migration Strategy](#migration-strategy)
9. [Frontend Integration](#frontend-integration)

---

## 1. Overview

### Purpose

Allow users to create and join **channels** (communities) where they can share posts with people who have similar interests. This is similar to:
- **Reddit's subreddits** (r/programming, r/news)
- **Blind's channels** (Tech Lounge, Job Referrals, Compensation)

### Key Features

| Feature | Description |
|---------|-------------|
| **Create Channel** | Users can create new channels with a name, description, and rules |
| **Join/Leave Channel** | Users can subscribe to channels they're interested in |
| **Post to Channel** | Posts belong to a specific channel |
| **Channel Discovery** | Browse and search for channels |
| **Channel Moderation** | Channel creators/admins can moderate content |
| **Channel Privacy** | Public or private channels |

---

## 2. Reference Platforms

### Reddit Structure
Source: [Reddit Architecture Overview](https://github.com/reddit-archive/reddit/wiki/architecture-overview)

```
┌─────────────────────────────────────────────────────────────┐
│                     REDDIT STRUCTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Subreddit (r/programming)                                   │
│  ├── Subscribers: 5.2M                                       │
│  ├── Moderators: [user1, user2, ...]                         │
│  ├── Rules: [rule1, rule2, ...]                              │
│  └── Posts                                                   │
│      ├── Post 1 (belongs_to: r/programming)                  │
│      │   └── Comments (nested)                               │
│      ├── Post 2                                              │
│      └── ...                                                 │
│                                                              │
│  Key Characteristics:                                        │
│  - One post belongs to ONE subreddit                         │
│  - Users can subscribe to multiple subreddits                │
│  - Subreddits have moderators (community-based moderation)   │
│  - Public/Private/Restricted visibility options              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Blind Structure
Source: [Blind App - Professional Community](https://apps.apple.com/us/app/blind-professional-community/id737534965)

```
┌─────────────────────────────────────────────────────────────┐
│                      BLIND STRUCTURE                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Channel Types:                                              │
│  1. Company Channels (private to company employees)          │
│     - Amazon, Google, Meta, etc.                             │
│     - Only verified employees can see/post                   │
│                                                              │
│  2. Topic Channels (public across companies)                 │
│     - Tech Lounge                                            │
│     - Job Referrals                                          │
│     - Compensation                                           │
│     - Interview Tips                                         │
│     - Layoffs                                                │
│                                                              │
│  Key Characteristics:                                        │
│  - Posts show author's company (anonymized username)         │
│  - Company channels require email verification               │
│  - Topic channels are public across all users                │
│  - Professional context (work-related content)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Data Model Design

### Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ENTITY RELATIONSHIPS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────┐         ┌───────────────────┐         ┌──────────┐            │
│  │   User   │────────▶│ ChannelMembership │◀────────│ Channel  │            │
│  │          │   1:N   │  (join table)     │   N:1   │          │            │
│  └──────────┘         └───────────────────┘         └──────────┘            │
│       │                        │                          │                  │
│       │ 1:N                    │                          │ 1:N              │
│       ▼                        │                          ▼                  │
│  ┌──────────┐                  │                    ┌──────────┐            │
│  │   Post   │──────────────────┼───────────────────▶│ Channel  │            │
│  │          │                  │          N:1       │          │            │
│  └──────────┘                  │                    └──────────┘            │
│       │                        │                                            │
│       │ 1:N                    │                                            │
│       ▼                        │                                            │
│  ┌──────────┐                  │                                            │
│  │ Comment  │                  │                                            │
│  │          │                  │                                            │
│  └──────────┘                  │                                            │
│                                │                                            │
│  Relationships:                │                                            │
│  - User creates Channel (creator_id)                                        │
│  - User joins Channel (ChannelMembership)                                   │
│  - Post belongs to Channel (channel_id, nullable for global posts)          │
│  - Channel has many Posts                                                   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Model Definitions

#### CommunityChannel Model

```python
class ChannelType(str, Enum):
    """Channel visibility/access type."""
    PUBLIC = "PUBLIC"       # Anyone can view and join
    PRIVATE = "PRIVATE"     # Invite-only, hidden from search
    RESTRICTED = "RESTRICTED"  # Anyone can view, join requires approval

class CommunityChannel(Base):
    """
    Community channel for grouping posts by topic/interest.

    Similar to Reddit subreddits or Blind channels.
    """
    __tablename__ = "community_channels"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    # Channel identity
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)  # URL-safe slug
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Visual identity
    icon_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Channel settings
    channel_type: Mapped[ChannelType] = mapped_column(
        Enum(ChannelType), default=ChannelType.PUBLIC, nullable=False
    )
    rules: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON or markdown

    # Statistics (denormalized for performance)
    member_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ownership
    creator_id: Mapped[str] = mapped_column(
        String(25), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Moderation
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_channels")
    members: Mapped[list["ChannelMembership"]] = relationship(back_populates="channel")
    posts: Mapped[list["Post"]] = relationship(back_populates="channel")
```

#### ChannelMembership Model (Join Table)

```python
class MemberRole(str, Enum):
    """Role within a channel."""
    MEMBER = "MEMBER"       # Regular member
    MODERATOR = "MODERATOR" # Can moderate content
    ADMIN = "ADMIN"         # Full channel control

class ChannelMembership(Base):
    """
    Many-to-many relationship between users and channels.

    Tracks membership, roles, and join date.
    """
    __tablename__ = "channel_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_channel_membership"),
    )

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(UUID, primary_key=True, default=uuid.uuid4)

    # Foreign keys
    user_id: Mapped[str] = mapped_column(
        String(25), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID, ForeignKey("community_channels.id", ondelete="CASCADE"), nullable=False
    )

    # Membership details
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole), default=MemberRole.MEMBER, nullable=False
    )

    # Notifications
    notifications_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="channel_memberships")
    channel: Mapped["CommunityChannel"] = relationship("CommunityChannel", back_populates="members")
```

#### Post Model Update

```python
# Add to existing Post model:

class Post(Base):
    # ... existing fields ...

    # NEW: Channel reference (nullable for global/uncategorized posts)
    channel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID, ForeignKey("community_channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # NEW: Relationship
    channel: Mapped["CommunityChannel | None"] = relationship(
        "CommunityChannel", back_populates="posts"
    )
```

---

## 4. Database Schema

### SQL Schema

```sql
-- Channel type enum
CREATE TYPE channel_type AS ENUM ('PUBLIC', 'PRIVATE', 'RESTRICTED');

-- Member role enum
CREATE TYPE member_role AS ENUM ('MEMBER', 'MODERATOR', 'ADMIN');

-- Community Channels table
CREATE TABLE community_channels (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Identity
    name VARCHAR(50) NOT NULL UNIQUE,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Visual
    icon_url VARCHAR(1000),
    banner_url VARCHAR(1000),

    -- Settings
    channel_type channel_type NOT NULL DEFAULT 'PUBLIC',
    rules TEXT,

    -- Statistics (denormalized)
    member_count INTEGER NOT NULL DEFAULT 0,
    post_count INTEGER NOT NULL DEFAULT 0,

    -- Ownership
    creator_id VARCHAR(25) REFERENCES users(id) ON DELETE SET NULL,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_archived BOOLEAN NOT NULL DEFAULT false,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for channels
CREATE INDEX ix_community_channels_name ON community_channels(name);
CREATE INDEX ix_community_channels_channel_type ON community_channels(channel_type);
CREATE INDEX ix_community_channels_creator_id ON community_channels(creator_id);
CREATE INDEX ix_community_channels_member_count ON community_channels(member_count DESC);

-- Channel Memberships table
CREATE TABLE channel_memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign keys
    user_id VARCHAR(25) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL REFERENCES community_channels(id) ON DELETE CASCADE,

    -- Membership details
    role member_role NOT NULL DEFAULT 'MEMBER',
    notifications_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Timestamps
    joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Unique constraint
    CONSTRAINT uq_channel_membership UNIQUE (user_id, channel_id)
);

-- Indexes for memberships
CREATE INDEX ix_channel_memberships_user_id ON channel_memberships(user_id);
CREATE INDEX ix_channel_memberships_channel_id ON channel_memberships(channel_id);
CREATE INDEX ix_channel_memberships_role ON channel_memberships(role);

-- Add channel_id to posts table
ALTER TABLE posts
ADD COLUMN channel_id UUID REFERENCES community_channels(id) ON DELETE SET NULL;

CREATE INDEX ix_posts_channel_id ON posts(channel_id);
```

---

## 5. API Endpoints

### Channel Management

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/channels` | Create new channel | Required |
| `GET` | `/api/v1/channels` | List channels (paginated) | Optional |
| `GET` | `/api/v1/channels/{name}` | Get channel by name | Optional* |
| `PATCH` | `/api/v1/channels/{id}` | Update channel | Admin/Creator |
| `DELETE` | `/api/v1/channels/{id}` | Delete channel (soft) | Admin/Creator |

### Channel Membership

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/channels/{id}/join` | Join channel | Required |
| `DELETE` | `/api/v1/channels/{id}/leave` | Leave channel | Required |
| `GET` | `/api/v1/channels/{id}/members` | List members | Member* |
| `PATCH` | `/api/v1/channels/{id}/members/{userId}` | Update member role | Admin |
| `DELETE` | `/api/v1/channels/{id}/members/{userId}` | Remove member | Admin/Mod |

### Channel Posts

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/channels/{id}/posts` | Get posts in channel | Optional* |
| `POST` | `/api/v1/channels/{id}/posts` | Create post in channel | Member |

### User's Channels

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `GET` | `/api/v1/users/me/channels` | Get user's joined channels | Required |
| `GET` | `/api/v1/users/me/channels/created` | Get user's created channels | Required |

*Note: Private channels require membership for access

### Request/Response Examples

#### Create Channel

```http
POST /api/v1/channels
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "tech-news",
  "display_name": "Tech News",
  "description": "Latest technology news and discussions",
  "channel_type": "PUBLIC",
  "rules": "1. Be respectful\n2. No spam\n3. Stay on topic"
}
```

```json
// Response: 201 Created
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "tech-news",
  "display_name": "Tech News",
  "description": "Latest technology news and discussions",
  "channel_type": "PUBLIC",
  "member_count": 1,
  "post_count": 0,
  "creator": {
    "id": "cm4xyz...",
    "name": "John Doe"
  },
  "is_member": true,
  "member_role": "ADMIN",
  "created_at": "2026-02-03T10:00:00Z"
}
```

#### List Channels

```http
GET /api/v1/channels?sort=popular&limit=20&offset=0
```

```json
// Response: 200 OK
{
  "items": [
    {
      "id": "...",
      "name": "tech-news",
      "display_name": "Tech News",
      "description": "Latest technology news...",
      "icon_url": "https://cdn.example.com/icons/tech.png",
      "member_count": 15420,
      "post_count": 3280,
      "is_member": false
    }
  ],
  "total": 156,
  "limit": 20,
  "offset": 0
}
```

---

## 6. Business Logic

### Channel Name Validation

```python
import re

CHANNEL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")
RESERVED_NAMES = {"admin", "api", "www", "help", "support", "all", "popular", "home"}

def validate_channel_name(name: str) -> bool:
    """
    Validate channel name.

    Rules:
    - 3-50 characters
    - Lowercase letters, numbers, hyphens only
    - Must start and end with letter or number
    - No consecutive hyphens
    - Not a reserved name
    """
    if name.lower() in RESERVED_NAMES:
        return False
    if "--" in name:
        return False
    return bool(CHANNEL_NAME_PATTERN.match(name.lower()))
```

### Join Channel Logic

```python
async def join_channel(
    channel_id: uuid.UUID,
    user_id: str,
    service: ChannelService
) -> ChannelMembership:
    """
    Join a channel.

    Flow:
    1. Check if channel exists and is active
    2. Check if user is already a member
    3. Check channel type permissions
    4. Create membership
    5. Increment member_count
    """
    channel = await service.get_channel(channel_id)

    if not channel or not channel.is_active:
        raise ChannelNotFoundError()

    existing = await service.get_membership(user_id, channel_id)
    if existing:
        raise AlreadyMemberError()

    if channel.channel_type == ChannelType.PRIVATE:
        raise ChannelPrivateError("Invite required to join")

    if channel.channel_type == ChannelType.RESTRICTED:
        # Create pending membership for approval
        return await service.create_pending_membership(user_id, channel_id)

    # PUBLIC channel - join immediately
    membership = await service.create_membership(user_id, channel_id)
    await service.increment_member_count(channel_id)

    return membership
```

### Post Creation in Channel

```python
async def create_post_in_channel(
    channel_id: uuid.UUID,
    user_id: str,
    title: str,
    content: str,
    service: PostService
) -> Post:
    """
    Create a post in a specific channel.

    Flow:
    1. Verify user is a member of the channel
    2. Create post with channel_id
    3. Increment channel's post_count
    """
    membership = await service.get_membership(user_id, channel_id)

    if not membership:
        raise NotMemberError("Must join channel to post")

    post = await service.create_post(
        user_id=user_id,
        title=title,
        content=content,
        channel_id=channel_id
    )

    await service.increment_post_count(channel_id)

    return post
```

---

## 7. Error Handling

### Domain Exceptions

```python
# channel/exceptions.py

class ChannelError(Exception):
    """Base exception for channel operations."""
    pass

class ChannelNotFoundError(ChannelError):
    """Channel does not exist or is inactive."""
    pass

class ChannelNameTakenError(ChannelError):
    """Channel name is already in use."""
    pass

class ChannelNameInvalidError(ChannelError):
    """Channel name does not meet requirements."""
    pass

class AlreadyMemberError(ChannelError):
    """User is already a member of the channel."""
    pass

class NotMemberError(ChannelError):
    """User is not a member of the channel."""
    pass

class ChannelPrivateError(ChannelError):
    """Channel is private and requires invitation."""
    pass

class InsufficientPermissionError(ChannelError):
    """User does not have required role for this action."""
    pass
```

### HTTP Error Mapping

```python
# channel/controller.py

@router.post("/{channel_id}/join")
async def join_channel(channel_id: uuid.UUID, ...):
    try:
        membership = await service.join_channel(channel_id, user_id)
        return MembershipResponse(...)
    except ChannelNotFoundError:
        raise HTTPException(404, "Channel not found")
    except AlreadyMemberError:
        raise HTTPException(409, "Already a member of this channel")
    except ChannelPrivateError:
        raise HTTPException(403, "Channel is private, invitation required")
```

---

## 8. Migration Strategy

### Phase 1: Database Setup

1. Create new tables (`community_channels`, `channel_memberships`)
2. Add `channel_id` column to `posts` table (nullable)
3. Create indexes

### Phase 2: API Implementation

1. Implement channel CRUD endpoints
2. Implement membership endpoints
3. Update post creation to support `channel_id`

### Phase 3: Data Migration (Optional)

If migrating existing posts to channels:

```sql
-- Create a "General" channel for existing posts
INSERT INTO community_channels (id, name, display_name, description)
VALUES (uuid_generate_v4(), 'general', 'General', 'General discussions');

-- Move existing posts (optional - or leave as null for "All" feed)
-- UPDATE posts SET channel_id = '<general-channel-id>' WHERE channel_id IS NULL;
```

### Phase 4: Frontend Integration

1. Add channel selection to post creation form
2. Add channel browsing/discovery UI
3. Add channel feed filtering
4. Add channel management UI for creators

---

## 9. Frontend Integration

### React Query Keys

```typescript
export const channelKeys = {
  all: ["channels"] as const,
  lists: () => [...channelKeys.all, "list"] as const,
  list: (filters: ChannelFilters) => [...channelKeys.lists(), filters] as const,
  details: () => [...channelKeys.all, "detail"] as const,
  detail: (nameOrId: string) => [...channelKeys.details(), nameOrId] as const,
  posts: (channelId: string) => [...channelKeys.detail(channelId), "posts"] as const,
  members: (channelId: string) => [...channelKeys.detail(channelId), "members"] as const,
};
```

### Jotai Atoms

```typescript
// Selected channel for filtering posts
export const selectedChannelAtom = atom<CommunityChannel | null>(null);

// Channel creation modal
export const isChannelCreateModalOpenAtom = atom(false);

// User's joined channels (cached)
export const userChannelsAtom = atom<CommunityChannel[]>([]);
```

### Post Creation Form Update

```typescript
interface PostCreateProps {
  channelId?: string;  // Pre-selected channel
}

function PostCreateForm({ channelId }: PostCreateProps) {
  const [selectedChannel, setSelectedChannel] = useState(channelId);

  // Fetch user's joined channels for dropdown
  const { data: userChannels } = useUserChannelsQuery();

  const handleSubmit = async () => {
    await createMutation.mutateAsync({
      title,
      content,
      channel_id: selectedChannel,  // NEW: Include channel
    });
  };

  return (
    <form>
      {/* Channel selector */}
      <select value={selectedChannel} onChange={...}>
        <option value="">All (No Channel)</option>
        {userChannels?.map(channel => (
          <option key={channel.id} value={channel.id}>
            {channel.display_name}
          </option>
        ))}
      </select>

      {/* ... existing form fields ... */}
    </form>
  );
}
```

---

## Summary

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Nullable channel_id on Post** | Allows "global" posts not tied to any channel (like Reddit's r/all) |
| **Denormalized counts** | `member_count` and `post_count` avoid expensive COUNT queries |
| **Separate membership table** | Supports roles, join dates, and notification preferences |
| **URL-safe name** | Enables clean URLs like `/c/tech-news` |
| **Soft delete for channels** | Preserves data while hiding channel from users |

### Implementation Order

1. Database schema and migrations
2. Channel CRUD API
3. Membership API
4. Update Post API to support channels
5. Frontend channel discovery
6. Frontend post creation with channel selector
7. Frontend channel management

---

## References

- [Reddit Architecture Overview](https://github.com/reddit-archive/reddit/wiki/architecture-overview)
- [Blind App - Professional Community](https://apps.apple.com/us/app/blind-professional-community/id737534965)
- [Reddit's Database Structure](https://kevin.burke.dev/kevin/reddits-database-has-two-tables/)
- [Blind: Building Anonymous Community](https://d3.harvard.edu/platform-digit/submission/blind-building-and-scaling-anonymous-community/)

---

*Created: 2026-02-03*
