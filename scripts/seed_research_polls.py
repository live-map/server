"""
Seed script for research-agent poll data.

Reads 10 research result markdown files (04~13), parses article text and sources,
then inserts Poll + PollOption + PollSource records into the database.

Usage:
    uv run python scripts/seed_research_polls.py
"""

import asyncio
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

USER_ID = "cm5test000000user01"

# UUID 101~110 (기존 시드 001~008과 충돌 방지)
RESEARCH_POLLS = [
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000101"),
        "file": "04-딥페이크.md",
        "title": "딥페이크 성범죄, 처벌을 더 강화해야 할까?",
        "description": "AI 딥페이크 기술을 악용한 성범죄 처벌 수준에 대한 의견을 수렴합니다.",
        "category": "사회",
        "options": ["처벌 대폭 강화", "현행 유지", "표현의 자유 우선"],
        "votes": [45200, 12800, 8600],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000102"),
        "file": "05-반려동물.md",
        "title": "반려동물 음식점 출입 허용, 찬성하십니까?",
        "description": "반려동물의 음식점 동반 출입 허용 여부에 대한 의견을 수렴합니다.",
        "category": "사회",
        "options": ["전면 허용", "조건부 허용", "허용 반대"],
        "votes": [15400, 38200, 22100],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000103"),
        "file": "06-다주택자.md",
        "title": "부동산 다주택자 규제, 어떻게 해야 할까?",
        "description": "주택 시장 안정을 위한 다주택자 규제 수준에 대한 의견을 수렴합니다.",
        "category": "경제",
        "options": ["규제 강화", "현행 유지", "규제 완화"],
        "votes": [41300, 18700, 25600],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000104"),
        "file": "07-구글맵.md",
        "title": "구글맵 국내 지도 반출 허용해야 할까?",
        "description": "구글의 국내 정밀지도 데이터 해외 반출 허용 여부에 대한 의견을 수렴합니다.",
        "category": "기술·사회",
        "options": ["전면 허용", "조건부 허용", "반출 불허"],
        "votes": [22100, 35800, 19500],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000105"),
        "file": "08-공매도.md",
        "title": "공매도 전면 재개, 어떻게 생각하십니까?",
        "description": "주식시장 공매도 재개 범위에 대한 의견을 수렴합니다.",
        "category": "경제",
        "options": ["전면 재개", "부분 재개", "금지 유지"],
        "votes": [18900, 29400, 37200],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000106"),
        "file": "09-AI기본법.md",
        "title": "AI 기본법 시행, 규제 수준은 적절한가?",
        "description": "2026년 시행 AI 기본법의 규제 수준 적절성에 대한 의견을 수렴합니다.",
        "category": "기술·사회",
        "options": ["규제 강화 필요", "현행 적절", "규제 완화 필요"],
        "votes": [28300, 21500, 16800],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000107"),
        "file": "10-부자증세.md",
        "title": "부자 증세 vs 감세, 어느 쪽이 맞을까?",
        "description": "고소득자·대기업 세금 정책 방향에 대한 의견을 수렴합니다.",
        "category": "경제",
        "options": ["증세 찬성", "현행 유지", "감세 찬성"],
        "votes": [34600, 19200, 22800],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000108"),
        "file": "11-선거권연령.md",
        "title": "지방선거 선거권 연령을 16세로 낮춰야 할까?",
        "description": "지방선거 선거권 연령 하향에 대한 의견을 수렴합니다.",
        "category": "정치",
        "options": ["16세 하향 찬성", "18세 유지", "하향 반대"],
        "votes": [19800, 25100, 31700],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000109"),
        "file": "12-원전확대.md",
        "title": "기후위기 대응, 원전 확대가 답인가?",
        "description": "기후위기 대응을 위한 에너지 정책 방향에 대한 의견을 수렴합니다.",
        "category": "사회",
        "options": ["원전 확대", "에너지 믹스", "재생에너지 집중"],
        "votes": [27400, 33100, 15900],
    },
    {
        "id": uuid.UUID("00000000-0000-4000-a000-000000000110"),
        "file": "13-고령운전.md",
        "title": "고령 운전자 면허 반납 의무화해야 할까?",
        "description": "고령 운전자의 면허 반납 정책에 대한 의견을 수렴합니다.",
        "category": "사회",
        "options": ["의무화 찬성", "자발적 유도", "의무화 반대"],
        "votes": [31200, 28500, 16900],
    },
]

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "research-results"


def clean_article(raw: str) -> str:
    """Clean up AI article text for frontend rendering."""
    # 1) Remove inline citations [^출처명|URL] — sources shown separately below
    text = re.sub(r"\[\^[^\|]+\|[^\]]+\]", "", raw)
    # 2) Downgrade ## to ### (article is inside h2 "투표 전 알아두면 좋은 팩트")
    text = re.sub(r"^## ", "### ", text, flags=re.MULTILINE)
    # 3) Clean up double spaces left by citation removal
    text = re.sub(r"  +", " ", text)
    # 4) Clean up space before punctuation (e.g. "있습니다 ." → "있습니다.")
    text = re.sub(r" ([.,])", r"\1", text)
    # 5) Remove empty lines that result from cleanup (keep max 1)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def parse_article(md_text: str) -> str:
    """Extract article text between '## 생성된 아티클' and the next '---'."""
    match = re.search(
        r"## 생성된 아티클\s*\n(.+?)(?=\n---)", md_text, re.DOTALL
    )
    if not match:
        raise ValueError("Could not find '## 생성된 아티클' section")
    return clean_article(match.group(1))


def parse_sources(md_text: str) -> list[dict]:
    """Parse web and academic source tables from the markdown."""
    sources: list[dict] = []

    for section, source_type in [("### 웹 출처", "NEWS"), ("### 학술 출처", "PAPER")]:
        pattern = re.escape(section) + r"\s*\n\|[^\n]+\n\|[^\n]+\n((?:\|[^\n]+\n?)*)"
        match = re.search(pattern, md_text)
        if not match:
            continue
        rows = match.group(1).strip().split("\n")
        for row in rows:
            cols = [c.strip() for c in row.split("|")]
            # cols: ['', '#', '제목', 'URL', '유형', '신뢰도', '']
            if len(cols) < 6:
                continue
            title = cols[2][:200]  # PollSource.title max 200
            url = cols[3]
            if not url.startswith("http"):
                continue
            sources.append({"title": title, "url": url, "source_type": source_type})

    return sources


async def seed(session: AsyncSession) -> None:
    now = datetime.now(timezone.utc)
    two_weeks = now + timedelta(days=14)

    # Clear existing seed data
    for poll in RESEARCH_POLLS:
        pid = poll["id"]
        await session.execute(
            text("DELETE FROM poll_sources WHERE poll_id = :pid"), {"pid": pid}
        )
        await session.execute(
            text("DELETE FROM poll_comments WHERE poll_id = :pid"), {"pid": pid}
        )
        await session.execute(
            text("DELETE FROM votes WHERE poll_id = :pid"), {"pid": pid}
        )
        await session.execute(
            text("DELETE FROM poll_options WHERE poll_id = :pid"), {"pid": pid}
        )
        await session.execute(
            text("DELETE FROM polls WHERE id = :pid"), {"pid": pid}
        )

    # Ensure test user exists (ignore conflict if already seeded)
    await session.execute(
        text("""
            INSERT INTO users (id, name, email, role, created_at, updated_at)
            VALUES (:id, :name, :email, :role, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING
        """),
        {
            "id": USER_ID,
            "name": "테스트유저",
            "email": "test@grapoll.kr",
            "role": "USER",
        },
    )

    total_sources = 0

    for poll in RESEARCH_POLLS:
        # Read and parse markdown
        md_path = DOCS_DIR / poll["file"]
        md_text = md_path.read_text(encoding="utf-8")
        ai_content = parse_article(md_text)
        sources = parse_sources(md_text)

        total_votes = sum(poll["votes"])

        # Insert poll
        await session.execute(
            text("""
                INSERT INTO polls
                    (id, user_id, title, description, image_url, category,
                     type, status, interaction_type, total_votes, view_count,
                     ai_content, ai_updated_at,
                     ends_at, created_at, updated_at, is_deleted)
                VALUES
                    (:id, :user_id, :title, :description, NULL, :category,
                     'OFFICIAL', 'ACTIVE', 'SINGLE_CHOICE', :total_votes, :view_count,
                     :ai_content, :ai_updated_at,
                     :ends_at, NOW(), NOW(), false)
            """),
            {
                "id": poll["id"],
                "user_id": USER_ID,
                "title": poll["title"],
                "description": poll["description"],
                "category": poll["category"],
                "total_votes": total_votes,
                "view_count": total_votes // 2,
                "ai_content": ai_content,
                "ai_updated_at": now,
                "ends_at": two_weeks,
            },
        )

        # Insert options
        for i, (opt_text, vote_count) in enumerate(
            zip(poll["options"], poll["votes"])
        ):
            await session.execute(
                text("""
                    INSERT INTO poll_options (id, poll_id, text, "order", vote_count)
                    VALUES (:id, :poll_id, :text, :ord, :vote_count)
                """),
                {
                    "id": uuid.uuid4(),
                    "poll_id": poll["id"],
                    "text": opt_text,
                    "ord": i,
                    "vote_count": vote_count,
                },
            )

        # Insert sources
        for src in sources:
            await session.execute(
                text("""
                    INSERT INTO poll_sources (id, poll_id, title, url, source_type, created_at)
                    VALUES (:id, :poll_id, :title, :url, :source_type, NOW())
                """),
                {
                    "id": uuid.uuid4(),
                    "poll_id": poll["id"],
                    "title": src["title"],
                    "url": src["url"],
                    "source_type": src["source_type"],
                },
            )
        total_sources += len(sources)

        print(f"  ✓ {poll['title']} ({len(sources)} sources)")

    await session.commit()
    print(f"\nSeeded: {len(RESEARCH_POLLS)} polls with options, ai_content, and {total_sources} sources")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
