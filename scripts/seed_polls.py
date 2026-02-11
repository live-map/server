"""
Seed script for poll data.

Inserts test user, polls, options, and comments into the database.
Based on the frontend mock data (V0_POLL_LIST, V0_HOT_DEBATES_BY_TYPE, V0_USER_POLLS).

Usage:
    uv run python scripts/seed_polls.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# Deterministic UUIDs for reproducibility
USER_ID = "cm5test000000user01"

POLL_IDS = {
    "hot_debate": uuid.UUID("00000000-0000-4000-a000-000000000001"),
    "ai_regulation": uuid.UUID("00000000-0000-4000-a000-000000000002"),
    "transit_free": uuid.UUID("00000000-0000-4000-a000-000000000003"),
    "remote_work": uuid.UUID("00000000-0000-4000-a000-000000000004"),
    "basic_income": uuid.UUID("00000000-0000-4000-a000-000000000005"),
    "suggested_1": uuid.UUID("00000000-0000-4000-a000-000000000006"),
    "suggested_2": uuid.UUID("00000000-0000-4000-a000-000000000007"),
    "suggested_3": uuid.UUID("00000000-0000-4000-a000-000000000008"),
}

now = datetime.now(timezone.utc)
two_weeks = now + timedelta(days=14)
one_week = now + timedelta(days=7)
three_days = now + timedelta(days=3)


async def seed(session: AsyncSession) -> None:
    # ===================== Clear existing seed data =====================
    for poll_id in POLL_IDS.values():
        await session.execute(
            text("DELETE FROM poll_comments WHERE poll_id = :pid"), {"pid": poll_id}
        )
        await session.execute(
            text("DELETE FROM votes WHERE poll_id = :pid"), {"pid": poll_id}
        )
        await session.execute(
            text("DELETE FROM poll_sources WHERE poll_id = :pid"), {"pid": poll_id}
        )
        await session.execute(
            text("DELETE FROM poll_options WHERE poll_id = :pid"), {"pid": poll_id}
        )
        await session.execute(
            text("DELETE FROM polls WHERE id = :pid"), {"pid": poll_id}
        )
    await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": USER_ID})

    # ===================== Test user =====================
    await session.execute(
        text("""
            INSERT INTO users (id, name, email, role, created_at, updated_at)
            VALUES (:id, :name, :email, :role, NOW(), NOW())
        """),
        {
            "id": USER_ID,
            "name": "테스트유저",
            "email": "test@grapoll.kr",
            "role": "USER",
        },
    )

    # ===================== Helper =====================
    async def insert_poll(
        poll_id: uuid.UUID,
        title: str,
        description: str | None,
        image_url: str | None,
        category: str,
        poll_type: str,
        interaction_type: str,
        total_votes: int,
        view_count: int,
        ends_at: datetime,
        options: list[dict],
        comments: list[dict] | None = None,
    ) -> None:
        await session.execute(
            text("""
                INSERT INTO polls
                    (id, user_id, title, description, image_url, category,
                     type, status, interaction_type, total_votes, view_count,
                     ends_at, created_at, updated_at, is_deleted)
                VALUES
                    (:id, :user_id, :title, :description, :image_url, :category,
                     :type, 'ACTIVE', :interaction_type, :total_votes, :view_count,
                     :ends_at, NOW(), NOW(), false)
            """),
            {
                "id": poll_id,
                "user_id": USER_ID,
                "title": title,
                "description": description,
                "image_url": image_url,
                "category": category,
                "type": poll_type,
                "interaction_type": interaction_type,
                "total_votes": total_votes,
                "view_count": view_count,
                "ends_at": ends_at,
            },
        )

        for i, opt in enumerate(options):
            opt_id = opt.get("id", uuid.uuid4())
            await session.execute(
                text("""
                    INSERT INTO poll_options (id, poll_id, text, "order", vote_count)
                    VALUES (:id, :poll_id, :text, :ord, :vote_count)
                """),
                {
                    "id": opt_id,
                    "poll_id": poll_id,
                    "text": opt["text"],
                    "ord": i,
                    "vote_count": opt.get("vote_count", 0),
                },
            )

        for c in (comments or []):
            await session.execute(
                text("""
                    INSERT INTO poll_comments
                        (id, poll_id, user_id, content, option_id, likes, depth,
                         created_at, updated_at, is_deleted)
                    VALUES
                        (:id, :poll_id, :user_id, :content, :option_id, :likes, 0,
                         NOW(), NOW(), false)
                """),
                {
                    "id": c.get("id", uuid.uuid4()),
                    "poll_id": poll_id,
                    "user_id": USER_ID,
                    "content": c["content"],
                    "option_id": c.get("option_id"),
                    "likes": c.get("likes", 0),
                },
            )

    # ===================== Hot Debate (BINARY) =====================
    opt_pro = uuid.UUID("00000000-0000-4000-b000-000000000001")
    opt_con = uuid.UUID("00000000-0000-4000-b000-000000000002")

    await insert_poll(
        poll_id=POLL_IDS["hot_debate"],
        title="AI 딥페이크 규제, 표현의 자유 vs 피해자 보호 어느 쪽이 우선일까요?",
        description="AI 딥페이크 기술의 확산에 따른 규제 방안을 논의합니다.",
        image_url="https://images.unsplash.com/photo-1677442136019-21780ecad995?w=400&h=300&fit=crop",
        category="기술·사회",
        poll_type="OFFICIAL",
        interaction_type="BINARY",
        total_votes=89420,
        view_count=42150,
        ends_at=two_weeks,
        options=[
            {"id": opt_pro, "text": "표현의 자유", "vote_count": 42166},
            {"id": opt_con, "text": "피해자 보호", "vote_count": 47254},
        ],
        comments=[
            {
                "content": "기술 발전을 막을 순 없지만 최소한의 가이드라인은 필요합니다",
                "option_id": opt_con,
                "likes": 234,
            },
            {
                "content": "과도한 규제는 기술 혁신을 저해할 수 있어요",
                "option_id": opt_pro,
                "likes": 189,
            },
            {
                "content": "선거철 딥페이크 영상이 진짜처럼 퍼지는 걸 보면 규제가 필요합니다",
                "option_id": opt_con,
                "likes": 156,
            },
            {
                "content": "AI 아트도 딥페이크 기술 기반입니다. 창작의 자유를 침해하면 안됩니다.",
                "option_id": opt_pro,
                "likes": 142,
            },
        ],
    )

    # ===================== General Polls =====================
    await insert_poll(
        poll_id=POLL_IDS["ai_regulation"],
        title="AI 규제 강화, 어떻게 생각하시나요?",
        description="인공지능 기술 규제 수준에 대한 국민 의견을 수렴합니다.",
        image_url="https://images.unsplash.com/photo-1529107386315-e1a2ed48a620?w=200&h=200&fit=crop",
        category="정치",
        poll_type="OFFICIAL",
        interaction_type="BINARY",
        total_votes=325000,
        view_count=580000,
        ends_at=two_weeks,
        options=[
            {"text": "규제 강화 찬성", "vote_count": 178750},
            {"text": "규제 완화 찬성", "vote_count": 146250},
        ],
    )

    await insert_poll(
        poll_id=POLL_IDS["transit_free"],
        title="대중교통 무료화, 현실적으로 가능할까?",
        description="대중교통 무료화가 교통 문제와 환경에 미칠 영향을 논의합니다.",
        image_url="https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?w=200&h=200&fit=crop",
        category="사회",
        poll_type="OFFICIAL",
        interaction_type="BINARY",
        total_votes=98000,
        view_count=215000,
        ends_at=one_week,
        options=[
            {"text": "가능하다", "vote_count": 43120},
            {"text": "불가능하다", "vote_count": 54880},
        ],
    )

    await insert_poll(
        poll_id=POLL_IDS["remote_work"],
        title="원격근무 의무화, 도입해야 할까?",
        description="포스트 코로나 시대, 원격근무 의무화에 대한 의견을 수렴합니다.",
        image_url="https://images.unsplash.com/photo-1497366216548-37526070297c?w=200&h=200&fit=crop",
        category="경제",
        poll_type="OFFICIAL",
        interaction_type="BINARY",
        total_votes=76000,
        view_count=165000,
        ends_at=one_week,
        options=[
            {"text": "의무화 찬성", "vote_count": 45600},
            {"text": "기업 자율에 맡겨야", "vote_count": 30400},
        ],
    )

    await insert_poll(
        poll_id=POLL_IDS["basic_income"],
        title="기본소득 도입, 찬성하시나요?",
        description="보편적 기본소득 도입의 찬반 의견을 수렴합니다.",
        image_url="https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=200&h=200&fit=crop",
        category="경제",
        poll_type="OFFICIAL",
        interaction_type="BINARY",
        total_votes=54000,
        view_count=120000,
        ends_at=three_days,
        options=[
            {"text": "찬성", "vote_count": 29700},
            {"text": "반대", "vote_count": 24300},
        ],
    )

    # ===================== Suggested (User) Polls =====================
    await insert_poll(
        poll_id=POLL_IDS["suggested_1"],
        title="국가위기관리단 신설, 어떻게 생각하시나요?",
        description="국가 위기 대응 전담 기구 신설에 대한 의견을 수렴합니다.",
        image_url=None,
        category="정치",
        poll_type="SUGGESTED",
        interaction_type="BINARY",
        total_votes=3046,
        view_count=1523,
        ends_at=two_weeks,
        options=[
            {"text": "찬성", "vote_count": 1827},
            {"text": "반대", "vote_count": 1219},
        ],
    )

    await insert_poll(
        poll_id=POLL_IDS["suggested_2"],
        title="공무원 정년 연장에 대한 찬반 의견이 궁금합니다",
        description="공무원 정년 65세 연장에 대한 의견을 나눕니다.",
        image_url=None,
        category="사회",
        poll_type="SUGGESTED",
        interaction_type="BINARY",
        total_votes=1784,
        view_count=892,
        ends_at=one_week,
        options=[
            {"text": "연장 찬성", "vote_count": 892},
            {"text": "현행 유지", "vote_count": 892},
        ],
    )

    await insert_poll(
        poll_id=POLL_IDS["suggested_3"],
        title="주 4일제 도입, 현실적으로 가능할까요?",
        description="주 4일 근무제의 현실 가능성에 대해 논의합니다.",
        image_url=None,
        category="경제",
        poll_type="SUGGESTED",
        interaction_type="BINARY",
        total_votes=1308,
        view_count=654,
        ends_at=two_weeks,
        options=[
            {"text": "가능하다", "vote_count": 784},
            {"text": "아직 시기상조", "vote_count": 524},
        ],
    )

    await session.commit()
    print(f"Seeded: 1 user, {len(POLL_IDS)} polls with options and comments")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
