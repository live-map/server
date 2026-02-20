"""seed 10 demo polls with votes and comments

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-02-20
"""

import json
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6g7h8i9j0"
down_revision: str | None = "d4e5f6g7h8i9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Seed Users ──────────────────────────────────────────────

SEED_USERS = [
    {"id": "demo_hackathon_user", "name": "Demo User", "email": "demo@grapoll.kr"},
    {"id": "seed_user_alice_001", "name": "김서연", "email": "alice@grapoll.kr"},
    {"id": "seed_user_bob_00002", "name": "이준혁", "email": "bob@grapoll.kr"},
    {"id": "seed_user_carol_003", "name": "박민지", "email": "carol@grapoll.kr"},
    {"id": "seed_user_dave_0004", "name": "최동현", "email": "dave@grapoll.kr"},
]

# ── Poll definitions ────────────────────────────────────────

POLLS = [
    {
        "title": "AI 규제 정책, 어디까지 필요할까?",
        "description": "인공지능 기술이 빠르게 발전하면서 규제의 필요성이 대두되고 있습니다. 적절한 AI 규제 수준은 어떠해야 할까요?",
        "interaction_type": "SINGLE_CHOICE",
        "category": "기술",
        "image_url": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&h=400&fit=crop",
        "options": ["강력한 규제 필요", "자율 규제 위주", "최소한의 안전 규제만", "규제 불필요"],
    },
    {
        "title": "대학 등록금 동결, 찬성하시나요?",
        "description": "물가 상승에도 불구하고 대학 등록금 동결 정책이 지속되고 있습니다. 이에 대한 의견은?",
        "interaction_type": "BINARY",
        "category": "교육",
        "image_url": "https://images.unsplash.com/photo-1523050854058-8df90110c476?w=800&h=400&fit=crop",
        "options": ["찬성", "반대"],
    },
    {
        "title": "주4일제 도입, 현실적으로 가능할까?",
        "description": "근로시간 단축과 삶의 질 향상을 위한 주4일제 논의가 활발합니다. 한국에서 주4일제가 실현 가능하다고 보시나요?",
        "interaction_type": "SINGLE_CHOICE",
        "category": "경제",
        "image_url": "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=800&h=400&fit=crop",
        "options": ["즉시 도입 가능", "단계적 도입 필요", "일부 업종만 가능", "시기상조"],
    },
    {
        "title": "기후변화 대응, 우선순위를 골라주세요",
        "description": "기후변화에 대응하기 위해 가장 시급하게 추진해야 할 정책은 무엇일까요? 복수 선택 가능합니다.",
        "interaction_type": "MULTIPLE_CHOICE",
        "category": "환경",
        "image_url": "https://images.unsplash.com/photo-1611273426858-450d8e3c9fce?w=800&h=400&fit=crop",
        "options": ["재생에너지 확대", "탄소세 도입", "전기차 보조금", "산림 복원", "플라스틱 규제"],
    },
    {
        "title": "현재 정치인 신뢰도를 점수로 매긴다면?",
        "description": "현재 한국 정치인들에 대한 전반적인 신뢰도를 1~10점으로 평가해 주세요.",
        "interaction_type": "SLIDER",
        "category": "정치",
        "image_url": "https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=800&h=400&fit=crop",
        "options": [],
    },
    {
        "title": "외국인이 가장 좋아하는 한국 음식 순위는?",
        "description": "해외에서 인기 있는 한국 음식의 순위를 매겨주세요. 드래그로 순서를 변경할 수 있습니다.",
        "interaction_type": "RANKING",
        "category": "문화",
        "image_url": "https://images.unsplash.com/photo-1498654896293-37aacf113fd9?w=800&h=400&fit=crop",
        "options": ["김치찌개", "비빔밥", "불고기", "떡볶이", "삼겹살"],
    },
    {
        "title": "SNS 실명제 도입, 찬성하시나요?",
        "description": "온라인 악성 댓글과 가짜뉴스 방지를 위해 SNS 실명제 도입이 논의되고 있습니다.",
        "interaction_type": "BINARY",
        "category": "사회",
        "image_url": "https://images.unsplash.com/photo-1611162617474-5b21e879e113?w=800&h=400&fit=crop",
        "options": ["찬성", "반대"],
    },
    {
        "title": "2026 월드컵 우승국 예측!",
        "description": "2026년 북중미 월드컵에서 우승할 팀은 어디일까요?",
        "interaction_type": "SINGLE_CHOICE",
        "category": "스포츠",
        "image_url": "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&h=400&fit=crop",
        "options": ["브라질", "아르헨티나", "프랑스", "독일", "대한민국"],
    },
    {
        "title": "재택근무가 생산성에 미치는 영향은?",
        "description": "코로나 이후 재택근무가 확산됐습니다. 재택근무가 업무 생산성에 어떤 영향을 준다고 생각하시나요?",
        "interaction_type": "SINGLE_CHOICE",
        "category": "경제",
        "image_url": "https://images.unsplash.com/photo-1585974738771-84483dd9f89f?w=800&h=400&fit=crop",
        "options": ["크게 향상", "약간 향상", "변화 없음", "약간 감소", "크게 감소"],
    },
    {
        "title": "핵발전소 확대, 찬성하시나요?",
        "description": "탄소중립 달성과 에너지 안보를 위해 핵발전소 추가 건설에 대한 의견은?",
        "interaction_type": "BINARY",
        "category": "환경",
        "image_url": "https://images.unsplash.com/photo-1591270551371-3401a1a9382f?w=800&h=400&fit=crop",
        "options": ["찬성", "반대"],
    },
]

# ── Sample comments ─────────────────────────────────────────

COMMENT_POOL = [
    "정말 중요한 주제라고 생각합니다.",
    "이 문제에 대해 더 많은 논의가 필요해요.",
    "공감합니다. 좋은 여론조사네요.",
    "다양한 관점에서 생각해볼 수 있는 주제입니다.",
    "결과가 궁금하네요!",
    "주변 사람들 의견도 다양하더라고요.",
    "이 부분은 좀 더 신중하게 접근해야 할 것 같아요.",
    "좋은 토론 주제입니다.",
    "데이터 기반으로 판단해야 하는 문제 같아요.",
    "양쪽 모두 일리가 있어 보입니다.",
    "현실적인 대안이 무엇인지가 중요하죠.",
    "시대의 변화에 맞춰 갈 필요가 있어요.",
    "이건 정말 논쟁적인 주제네요.",
    "한 번 더 생각해보게 되는 설문입니다.",
    "재미있는 주제! 결과 공유해주세요.",
]


def _deterministic_uuid(namespace: str, index: int) -> str:
    """Generate a deterministic UUID from a namespace string + index."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"grapoll.seed.{namespace}.{index}"))


def upgrade() -> None:
    conn = op.get_bind()

    # ── 1. Delete existing poll data (cascades handle votes/comments/options) ──
    conn.execute(sa.text("DELETE FROM poll_comment_likes"))
    conn.execute(sa.text("DELETE FROM poll_comments"))
    conn.execute(sa.text("DELETE FROM votes"))
    conn.execute(sa.text("DELETE FROM poll_sources"))
    conn.execute(sa.text("DELETE FROM poll_options"))
    conn.execute(sa.text("DELETE FROM polls"))

    # ── 2. Ensure seed users exist ──
    for u in SEED_USERS:
        conn.execute(
            sa.text(
                """
                INSERT INTO users (id, name, email, role, created_at, updated_at)
                VALUES (:id, :name, :email, 'USER', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            u,
        )

    user_ids = [u["id"] for u in SEED_USERS]

    # ── 3. Create polls + options ──
    for poll_idx, poll_def in enumerate(POLLS):
        poll_id = _deterministic_uuid("poll", poll_idx)
        author_id = user_ids[poll_idx % len(user_ids)]

        hours_offset = (len(POLLS) - poll_idx) * 6
        conn.execute(
            sa.text(
                """
                INSERT INTO polls (id, user_id, title, description, image_url, category,
                    type, status, interaction_type, total_votes, view_count,
                    created_at, updated_at)
                VALUES (:id, :user_id, :title, :description, :image_url, :category,
                    'SUGGESTED', 'ACTIVE', :interaction_type, 0, :view_count,
                    NOW() - make_interval(hours => :hours_offset), NOW())
                """
            ),
            {
                "id": poll_id,
                "user_id": author_id,
                "title": poll_def["title"],
                "description": poll_def["description"],
                "image_url": poll_def.get("image_url"),
                "category": poll_def["category"],
                "interaction_type": poll_def["interaction_type"],
                "view_count": (poll_idx + 1) * 37 % 200 + 50,
                "hours_offset": hours_offset,
            },
        )

        # Create options
        option_ids = []
        for opt_idx, opt_text in enumerate(poll_def["options"]):
            option_id = _deterministic_uuid(f"poll{poll_idx}.option", opt_idx)
            option_ids.append(option_id)
            conn.execute(
                sa.text(
                    """
                    INSERT INTO poll_options (id, poll_id, text, "order", vote_count)
                    VALUES (:id, :poll_id, :text, :order, 0)
                    """
                ),
                {
                    "id": option_id,
                    "poll_id": poll_id,
                    "text": opt_text,
                    "order": opt_idx,
                },
            )

        # ── 4. Generate votes ──
        itype = poll_def["interaction_type"]
        num_votes = 20 + ((poll_idx * 7 + 13) % 61)  # 20~80 deterministic
        vote_user_cycle = user_ids * ((num_votes // len(user_ids)) + 1)

        # Track per-option vote counts for denormalization
        option_vote_counts: dict[str, int] = {oid: 0 for oid in option_ids}

        for v_idx in range(num_votes):
            vote_id = _deterministic_uuid(f"poll{poll_idx}.vote", v_idx)
            voter_id = vote_user_cycle[v_idx % len(vote_user_cycle)]

            # Only one vote per user per poll – skip duplicates
            if v_idx >= len(user_ids):
                # We've exhausted unique users; stop
                num_votes = len(user_ids)
                break

            if itype in ("SINGLE_CHOICE", "BINARY"):
                chosen_idx = v_idx % len(option_ids) if option_ids else 0
                chosen_option = option_ids[chosen_idx]
                option_vote_counts[chosen_option] += 1
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO votes (id, user_id, poll_id, option_id, created_at)
                        VALUES (:id, :user_id, :poll_id, :option_id, NOW())
                        ON CONFLICT ON CONSTRAINT uq_votes_user_poll DO NOTHING
                        """
                    ),
                    {
                        "id": vote_id,
                        "user_id": voter_id,
                        "poll_id": poll_id,
                        "option_id": chosen_option,
                    },
                )

            elif itype == "MULTIPLE_CHOICE":
                # Each voter selects 2-3 options
                num_selected = 2 + (v_idx % 2)
                selected = [option_ids[i % len(option_ids)] for i in range(v_idx, v_idx + num_selected)]
                selected = list(dict.fromkeys(selected))  # dedupe preserving order
                for sel_id in selected:
                    option_vote_counts[sel_id] += 1
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO votes (id, user_id, poll_id, selected_option_ids, created_at)
                        VALUES (:id, :user_id, :poll_id, :selected, NOW())
                        ON CONFLICT ON CONSTRAINT uq_votes_user_poll DO NOTHING
                        """
                    ),
                    {
                        "id": vote_id,
                        "user_id": voter_id,
                        "poll_id": poll_id,
                        "selected": json.dumps(selected),
                    },
                )

            elif itype == "SLIDER":
                val = 1 + (v_idx * 17 + 3) % 10  # 1~10 deterministic
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO votes (id, user_id, poll_id, slider_value, created_at)
                        VALUES (:id, :user_id, :poll_id, :slider_value, NOW())
                        ON CONFLICT ON CONSTRAINT uq_votes_user_poll DO NOTHING
                        """
                    ),
                    {
                        "id": vote_id,
                        "user_id": voter_id,
                        "poll_id": poll_id,
                        "slider_value": val,
                    },
                )

            elif itype == "RANKING":
                # Rotate the ranking order per voter
                rotated = option_ids[v_idx % len(option_ids):] + option_ids[:v_idx % len(option_ids)]
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO votes (id, user_id, poll_id, ranking_data, created_at)
                        VALUES (:id, :user_id, :poll_id, :ranking, NOW())
                        ON CONFLICT ON CONSTRAINT uq_votes_user_poll DO NOTHING
                        """
                    ),
                    {
                        "id": vote_id,
                        "user_id": voter_id,
                        "poll_id": poll_id,
                        "ranking": json.dumps(rotated),
                    },
                )

        # Update denormalized counters
        actual_votes = min(num_votes, len(user_ids))
        conn.execute(
            sa.text("UPDATE polls SET total_votes = :count WHERE id = :id"),
            {"count": actual_votes, "id": poll_id},
        )
        for oid, cnt in option_vote_counts.items():
            if cnt > 0:
                conn.execute(
                    sa.text("UPDATE poll_options SET vote_count = :count WHERE id = :id"),
                    {"count": cnt, "id": oid},
                )

        # ── 5. Generate comments ──
        num_comments = 3 + (poll_idx * 3 + 2) % 8  # 3~10 deterministic
        for c_idx in range(num_comments):
            comment_id = _deterministic_uuid(f"poll{poll_idx}.comment", c_idx)
            commenter_id = user_ids[c_idx % len(user_ids)]
            comment_text = COMMENT_POOL[(poll_idx * 3 + c_idx) % len(COMMENT_POOL)]
            # Assign comment to a random option (for sided comments)
            comment_option_id = option_ids[c_idx % len(option_ids)] if option_ids else None

            if comment_option_id:
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO poll_comments (id, poll_id, user_id, option_id, content, likes, depth, created_at, updated_at, is_deleted)
                        VALUES (:id, :poll_id, :user_id, :option_id, :content, :likes, 0, NOW(), NOW(), false)
                        """
                    ),
                    {
                        "id": comment_id,
                        "poll_id": poll_id,
                        "user_id": commenter_id,
                        "option_id": comment_option_id,
                        "content": comment_text,
                        "likes": c_idx % 5,
                    },
                )
            else:
                conn.execute(
                    sa.text(
                        """
                        INSERT INTO poll_comments (id, poll_id, user_id, content, likes, depth, created_at, updated_at, is_deleted)
                        VALUES (:id, :poll_id, :user_id, :content, :likes, 0, NOW(), NOW(), false)
                        """
                    ),
                    {
                        "id": comment_id,
                        "poll_id": poll_id,
                        "user_id": commenter_id,
                        "content": comment_text,
                        "likes": c_idx % 5,
                    },
                )


def downgrade() -> None:
    conn = op.get_bind()

    # Delete seeded data by deterministic IDs
    for poll_idx in range(len(POLLS)):
        poll_id = _deterministic_uuid("poll", poll_idx)
        # Cascade will handle options, votes, comments
        conn.execute(
            sa.text("DELETE FROM polls WHERE id = :id"),
            {"id": poll_id},
        )

    # Remove seed users (except demo_hackathon_user which belongs to previous migration)
    for u in SEED_USERS[1:]:
        conn.execute(
            sa.text("DELETE FROM users WHERE id = :id"),
            {"id": u["id"]},
        )
