"""
Unified demo seed script with AI research content.

Clears ALL poll data and re-seeds with rich demo polls including:
- ai_content (markdown article)
- poll_sources (news + paper references)
- poll_comments with option_id tags
- Realistic vote counts and view counts
- Multiple interaction types (BINARY, SINGLE_CHOICE, RANKING, SLIDER)

Usage:
    uv run python scripts/seed_demo.py
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# ──────────────────── Users ────────────────────
USERS = [
    {"id": "cm5demo00000user01", "name": "최동현", "email": "donghan@grapoll.kr"},
    {"id": "cm5demo00000user02", "name": "김서연", "email": "seoyeon@grapoll.kr"},
    {"id": "cm5demo00000user03", "name": "이준혁", "email": "junhyuk@grapoll.kr"},
    {"id": "cm5demo00000user04", "name": "박민지", "email": "minji@grapoll.kr"},
    {"id": "cm5demo00000user05", "name": "한소율", "email": "soyul@grapoll.kr"},
]

# ──────────────────── Poll data ────────────────────

now = datetime.now(timezone.utc)

POLLS = [
    # ───── 1. 딥페이크 (BINARY, Hot Debate) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000001"),
        "user_idx": 0,
        "title": "딥페이크 규제, 표현의 자유 vs 피해자 보호 어느 쪽이 우선?",
        "description": "AI 딥페이크 기술의 확산에 따른 규제 방안을 논의합니다. 창작과 표현의 자유를 보장하면서도 피해자를 보호할 수 있는 균형점은 어디일까요?",
        "image_url": "https://images.unsplash.com/photo-1677442136019-21780ecad995?w=800&h=400&fit=crop",
        "category": "사회",
        "poll_type": "OFFICIAL",
        "interaction_type": "BINARY",
        "total_votes": 89420,
        "view_count": 142150,
        "ends_at": now + timedelta(days=14),
        "options": [
            {"text": "표현의 자유 우선", "vote_count": 42166},
            {"text": "피해자 보호 우선", "vote_count": 47254},
        ],
        "ai_content": """### 딥페이크 기술의 현재와 규제 논란

딥페이크(Deepfake)는 딥러닝 기반 AI가 사람의 얼굴·음성을 합성하는 기술입니다. 2024년 기준 전 세계 딥페이크 영상은 **약 95,820건**으로 전년 대비 550% 증가했으며, 이 중 **98%가 비동의 음란물**로 분류됩니다.

### 피해자 보호 강화 입장

한국은 2024년 「성폭력처벌법」 개정을 통해 딥페이크 성범죄 처벌을 **최대 7년 이하 징역**으로 강화했습니다. 여성가족부 실태조사에 따르면 피해자의 **73%가 10~20대 여성**이며, 피해 영상 삭제율은 **22%**에 불과합니다. 영국·호주 등은 동의 없는 딥페이크 배포에 형사처벌을 도입했고, EU의 AI Act는 딥페이크 콘텐츠에 **의무 라벨링**을 요구합니다.

### 표현의 자유 우선 입장

반면, 딥페이크는 영화 VFX·교육·예술 등 **합법적 활용 가치**가 큽니다. 미국에서는 수정헌법 제1조를 근거로 "기술 자체가 아닌 악용 행위만 규제해야 한다"는 주장이 유력합니다. AI 창작 도구 규제가 과도할 경우 **연 120조원** 규모의 생성형 AI 산업 성장이 위축될 수 있다는 우려도 있습니다.

### 해외 사례와 전망

EU AI Act(2024)는 딥페이크를 '제한적 위험'으로 분류해 투명성 의무를 부과하되 전면 금지는 피했습니다. 한국 방통위는 2025년 **AI 워터마크 의무화**를 추진 중이며, 기술적 탐지와 법적 규제를 병행하는 '이중 안전장치' 접근이 국제 표준으로 자리잡고 있습니다.""",
        "sources": [
            {"title": "2024 딥페이크 현황 보고서 - Sensity AI", "url": "https://sensity.ai/deepfake-report-2024", "source_type": "NEWS"},
            {"title": "성폭력처벌법 개정안 주요 내용", "url": "https://www.law.go.kr/lsInfoP.do?lsiSeq=256123", "source_type": "NEWS"},
            {"title": "EU AI Act: Implications for Deepfake Regulation", "url": "https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai", "source_type": "PAPER"},
            {"title": "Deepfakes and Democracy: AI-Generated Media", "url": "https://www.brookings.edu/articles/deepfakes-and-democracy", "source_type": "PAPER"},
        ],
        "comments": [
            {"user_idx": 1, "content": "기술 발전을 막을 순 없지만 최소한의 가이드라인은 필요합니다", "option_idx": 1, "likes": 234},
            {"user_idx": 2, "content": "과도한 규제는 기술 혁신을 저해할 수 있어요", "option_idx": 0, "likes": 189},
            {"user_idx": 3, "content": "선거철 딥페이크 영상이 진짜처럼 퍼지는 걸 보면 규제가 필요합니다", "option_idx": 1, "likes": 156},
            {"user_idx": 4, "content": "AI 아트도 딥페이크 기술 기반입니다. 창작의 자유를 침해하면 안됩니다", "option_idx": 0, "likes": 142},
            {"user_idx": 0, "content": "워터마크 의무화가 현실적인 대안이 될 수 있을 것 같아요", "option_idx": 1, "likes": 98},
        ],
    },

    # ───── 2. 공매도 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000002"),
        "user_idx": 1,
        "title": "공매도 전면 재개, 어떻게 생각하십니까?",
        "description": "2025년 3월 공매도가 전면 재개되었습니다. 주식시장에 미치는 영향과 개인 투자자 보호에 대한 의견을 수렴합니다.",
        "image_url": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&h=400&fit=crop",
        "category": "경제",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 85500,
        "view_count": 198000,
        "ends_at": now + timedelta(days=10),
        "options": [
            {"text": "전면 재개 찬성", "vote_count": 18900},
            {"text": "개인투자자 참여 조건부 재개", "vote_count": 29400},
            {"text": "기관만 허용", "vote_count": 12800},
            {"text": "전면 금지 유지", "vote_count": 24400},
        ],
        "ai_content": """### 공매도란 무엇인가

공매도(Short Selling)란 보유하지 않은 주식을 빌려 매도한 후, 가격이 하락하면 싸게 사서 갚아 차익을 얻는 투자 전략입니다. 한국 증시에서는 2023년 11월 불법 공매도 사태를 계기로 전면 금지되었다가 **2025년 3월 31일** 전면 재개되었습니다.

### 재개 찬성 입장

금융위원회는 공매도가 **가격 발견 기능**을 수행하며, MSCI 선진국 지수 편입 조건 중 하나라고 설명합니다. 실제로 공매도 금지 기간 중 코스피 거래대금은 **일평균 8.2조원**에서 **6.1조원**으로 25% 감소했습니다. 글로벌 기관투자자들은 공매도 허용을 투자 조건으로 제시하고 있어, 해외자금 유입에 필수적입니다.

### 반대·조건부 입장

개인 투자자들은 기관과의 **정보 비대칭**을 가장 큰 문제로 지적합니다. 2023년 적발된 불법 무차입 공매도 규모는 **약 55.6조원**으로, "같은 룰로 경쟁한 적이 없다"는 불신이 깊습니다. 한국주식투자자연합회 조사에서 개인 투자자의 **78.3%**가 공매도 재개에 반대했습니다.

### 제도 개선 현황

금융위는 재개와 함께 ①공매도 전산시스템(NSDS) 도입 ②무차입 공매도 형사처벌 강화(5년→10년) ③개인 공매도 참여 확대(대차 수수료 인하) 등 보완책을 시행했습니다. 다만 전문가들은 "시스템만으로 불법을 100% 막을 수 없다"며 **실시간 모니터링 인력 확충**이 필요하다고 지적합니다.""",
        "sources": [
            {"title": "금융위원회 공매도 재개 방안 발표", "url": "https://www.fsc.go.kr/no010101/80435", "source_type": "NEWS"},
            {"title": "코스피 공매도 금지와 시장 유동성 분석", "url": "https://www.kcmi.re.kr/publications/pub_detail_view?syear=2025", "source_type": "PAPER"},
            {"title": "Short Selling Bans: Evidence from Korea", "url": "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4812345", "source_type": "PAPER"},
        ],
        "comments": [
            {"user_idx": 2, "content": "기관이 같은 룰로 하는지가 문제죠. 전산시스템 잘 되면 찬성합니다", "option_idx": 1, "likes": 312},
            {"user_idx": 3, "content": "MSCI 선진국 편입하려면 공매도 허용은 필수입니다", "option_idx": 0, "likes": 187},
            {"user_idx": 4, "content": "55조 불법 공매도 처벌도 제대로 안 했으면서 재개라니", "option_idx": 3, "likes": 276},
            {"user_idx": 0, "content": "개인도 참여할 수 있게 해주면 공정하다고 봅니다", "option_idx": 1, "likes": 143},
        ],
    },

    # ───── 3. AI 기본법 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000003"),
        "user_idx": 2,
        "title": "AI 기본법 시행, 규제 수준은 적절한가?",
        "description": "2026년 1월 시행된 AI 기본법의 규제 수준에 대한 국민 의견을 수렴합니다.",
        "image_url": "https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=800&h=400&fit=crop",
        "category": "기술",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 66600,
        "view_count": 112000,
        "ends_at": now + timedelta(days=21),
        "options": [
            {"text": "규제 더 강화 필요", "vote_count": 28300},
            {"text": "현행 적절", "vote_count": 21500},
            {"text": "규제 완화 필요", "vote_count": 16800},
        ],
        "ai_content": """### AI 기본법이란

「인공지능 산업 육성 및 신뢰 확보에 관한 기본법」(AI 기본법)은 한국 최초의 AI 전문 법률로, **2026년 1월 22일** 시행되었습니다. AI 기술 개발·활용의 기본 원칙을 정하고, '고위험 AI'에 대한 사전·사후 관리 체계를 도입했습니다.

### 주요 내용

이 법은 AI를 위험도에 따라 분류합니다. **고위험 AI**(의료 진단, 채용 심사, 자율주행 등)는 사전 영향평가와 투명성 보고가 의무화되며, **초거대 AI**(GPT급 대형 모델)는 출시 전 안전성 검증을 받아야 합니다. 위반 시 **매출액 3% 이하 과징금**이 부과됩니다.

### 규제 강화 입장

시민단체와 노동계는 "현행법은 산업 육성에 치우쳐 있다"고 비판합니다. 실제로 고위험 AI 분류 기준이 **EU AI Act** 대비 좁고, AI에 의한 차별·편향 피해 구제 절차가 미비합니다. 참여연대는 "AI 피해자 집단소송 제도"와 "알고리즘 감사 의무화"를 추가 입법 사항으로 요구하고 있습니다.

### 규제 완화 입장

IT 업계는 과도한 규제가 **AI 스타트업의 글로벌 경쟁력**을 저해한다고 주장합니다. 한국AI산업협회에 따르면, 사전 영향평가 비용이 중소기업 기준 **평균 2.3억원**으로 부담이 크며, "혁신 먼저, 규제 나중" 원칙을 적용한 싱가포르·UAE 대비 불리하다는 입장입니다. KAIST 연구팀은 현행법이 시행될 경우 국내 AI 투자가 **15~20% 위축**될 수 있다고 전망했습니다.

### 국제 비교

EU AI Act는 전면 금지(사회적 점수 부여 등) → 고위험 → 제한적 위험 → 최소 위험의 **4단계 분류**를 적용하는 반면, 한국은 2단계(고위험/일반)로 단순합니다. 미국은 연방 차원 포괄 규제 없이 주별·분야별 접근을 택하고 있습니다.""",
        "sources": [
            {"title": "AI 기본법 전문 - 국가법령정보센터", "url": "https://www.law.go.kr/lsInfoP.do?lsiSeq=260234", "source_type": "NEWS"},
            {"title": "EU AI Act와 한국 AI 기본법 비교 분석", "url": "https://www.kisdi.re.kr/report/view.do?key=m2101113025724", "source_type": "PAPER"},
            {"title": "Impact of AI Regulation on Startup Investment", "url": "https://arxiv.org/abs/2501.12345", "source_type": "PAPER"},
        ],
        "comments": [
            {"user_idx": 0, "content": "AI 채용 심사에서 성별 차별 사례가 이미 나오고 있는데 규제 강화 필요합니다", "option_idx": 0, "likes": 201},
            {"user_idx": 3, "content": "스타트업 입장에서 영향평가 비용이 진입장벽이 됩니다", "option_idx": 2, "likes": 167},
            {"user_idx": 4, "content": "EU 수준까지는 아니더라도 현재 수준이면 적절하다고 봅니다", "option_idx": 1, "likes": 98},
        ],
    },

    # ───── 4. 부자 증세 (BINARY) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000004"),
        "user_idx": 3,
        "title": "부자 증세 vs 감세, 어느 쪽이 맞을까?",
        "description": "고소득자·대기업 세금 정책 방향에 대한 의견을 수렴합니다.",
        "image_url": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=800&h=400&fit=crop",
        "category": "경제",
        "poll_type": "OFFICIAL",
        "interaction_type": "BINARY",
        "total_votes": 76600,
        "view_count": 134000,
        "ends_at": now + timedelta(days=12),
        "options": [
            {"text": "증세가 맞다", "vote_count": 42130},
            {"text": "감세가 맞다", "vote_count": 34470},
        ],
        "ai_content": """### 한국의 소득세 구조

한국의 소득세 최고세율은 **45%**(과세표준 10억원 초과)로, OECD 평균(42.8%)보다 높은 편입니다. 법인세 최고세율은 **24%**이며, 2023년부터 25%→24%로 인하되었습니다. 상위 1% 소득자가 전체 소득세의 **약 42%**를 부담하고 있습니다.

### 증세 찬성 입장

소득 불평등 심화가 핵심 근거입니다. 2024년 기준 한국의 자산 상위 10%가 전체 부의 **58.7%**를 보유하고 있으며, 소득 5분위 배율은 **6.8배**로 OECD 평균(5.4배)을 상회합니다. 경제정의실천시민연합은 "부유세 도입과 자본이득세 강화가 재정 건전성 확보와 복지 재원 마련에 필수적"이라고 주장합니다. IMF도 "극단적 불평등은 경제 성장을 저해한다"는 연구 결과를 발표한 바 있습니다.

### 감세 찬성 입장

한국경영자총협회는 "높은 세율이 해외 자본 유출과 투자 위축을 초래한다"고 주장합니다. 실제로 2024년 국내 대기업의 해외 직접투자(ODI)는 **전년 대비 18% 증가**했으며, 일부는 세금 부담을 이유로 꼽았습니다. 낙수효과(Trickle-down) 이론에 따르면, 기업과 고소득층의 세금을 낮추면 투자·소비가 늘어 경제 전체에 혜택이 돌아간다는 논리입니다.

### 국제 비교

북유럽 모델(덴마크 최고 55.9%)은 높은 세율 + 강력한 복지를 결합하여 소득 불평등을 낮추는 데 성공했습니다. 반면 아일랜드(법인세 12.5%)는 낮은 세율로 글로벌 기업을 유치해 경제 성장을 이뤘습니다. 정답은 하나가 아니며, **재정 상황과 복지 수준의 균형**이 핵심입니다.""",
        "sources": [
            {"title": "OECD 소득 불평등 보고서 2024", "url": "https://www.oecd.org/social/inequality.htm", "source_type": "PAPER"},
            {"title": "국세통계연보 - 소득세 분위별 현황", "url": "https://stats.nts.go.kr/national/major_detail.asp", "source_type": "NEWS"},
            {"title": "Causes and Consequences of Income Inequality - IMF", "url": "https://www.imf.org/external/pubs/ft/sdn/2015/sdn1513.pdf", "source_type": "PAPER"},
        ],
        "comments": [
            {"user_idx": 0, "content": "상위 1%가 42% 부담하면 충분한 거 아닌가요?", "option_idx": 1, "likes": 198},
            {"user_idx": 1, "content": "자산 격차는 소득세만으로 안 줄어요. 부유세가 필요합니다", "option_idx": 0, "likes": 234},
            {"user_idx": 4, "content": "북유럽처럼 높은 세금 + 강한 복지면 납득할 수 있어요", "option_idx": 0, "likes": 156},
        ],
    },

    # ───── 5. 고령 운전 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000005"),
        "user_idx": 4,
        "title": "고령 운전자 면허 반납 의무화해야 할까?",
        "description": "고령 운전자 교통사고 증가에 따른 면허 반납 정책의 방향을 논의합니다.",
        "image_url": "https://images.unsplash.com/photo-1494976388531-d1058494cdd8?w=800&h=400&fit=crop",
        "category": "사회",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 76600,
        "view_count": 125000,
        "ends_at": now + timedelta(days=18),
        "options": [
            {"text": "일정 나이 이상 의무 반납", "vote_count": 31200},
            {"text": "적성검사 강화로 자발적 유도", "vote_count": 28500},
            {"text": "의무화 반대 (이동권 보장)", "vote_count": 16900},
        ],
        "ai_content": """### 고령 운전 사고 현황

경찰청 통계에 따르면 2024년 65세 이상 고령 운전자 교통사고는 **39,247건**으로 전체 사고의 **18.2%**를 차지하며, 5년 전(12.4%) 대비 크게 증가했습니다. 고령 운전자 사고 치사율은 **2.8%**로 전체 평균(1.4%)의 2배입니다.

### 의무 반납 찬성 입장

도로교통공단 연구에 따르면 75세 이상 운전자의 **인지반응 속도**는 30대 대비 평균 40% 느리며, 야간 시력은 **60% 감소**합니다. 일본은 2017년부터 75세 이상 면허 갱신 시 **인지기능 검사를 의무화**했고, 치매 판정자는 면허가 취소됩니다. 시행 후 75세 이상 사고가 **15% 감소**했습니다.

### 의무화 반대 입장

대한노인회는 "면허 반납은 사실상 이동권 박탈"이라고 반대합니다. 특히 **농어촌 고령자의 87%**가 자가용을 유일한 교통수단으로 이용하고 있어, 대중교통 대안 없는 반납은 생존권 침해에 해당한다는 주장입니다. 한국교통연구원은 "반납 의무화보다 **고령자 맞춤 교통 인프라 확충**이 선행되어야 한다"고 권고합니다.

### 자발적 반납 현황

정부는 면허 자진 반납 시 교통카드 10만원, 택시비 할인 등 인센티브를 제공하고 있으나, 반납률은 연간 **3.2%**에 불과합니다. 서울시의 경우 반납 후 **무료 대중교통권**을 제공하여 반납률이 5.1%로 높아졌지만, 지방은 인프라 부족으로 효과가 미미합니다.""",
        "sources": [
            {"title": "2024 교통사고 통계분석 - 경찰청", "url": "https://www.police.go.kr/www/open/publice/publice0201.jsp", "source_type": "NEWS"},
            {"title": "고령운전자 인지능력과 사고위험 상관관계 연구", "url": "https://www.koti.re.kr/component/file/ND_fileDownload.do", "source_type": "PAPER"},
            {"title": "Japan's Cognitive Function Test for Elderly Drivers", "url": "https://www.npa.go.jp/english/bureau/traffic/elderly.html", "source_type": "NEWS"},
        ],
        "comments": [
            {"user_idx": 0, "content": "시골 어르신들은 차 없으면 병원도 못 갑니다. 대안 먼저!", "option_idx": 2, "likes": 287},
            {"user_idx": 1, "content": "일본처럼 인지기능 검사 의무화가 가장 합리적이라 봅니다", "option_idx": 1, "likes": 213},
            {"user_idx": 2, "content": "사고 치사율이 2배면 도로 위 시한폭탄 아닌가요", "option_idx": 0, "likes": 176},
        ],
    },

    # ───── 6. 반려동물 음식점 출입 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000006"),
        "user_idx": 0,
        "title": "반려동물 음식점 출입 허용, 찬성하십니까?",
        "description": "반려인구 1,500만 시대, 반려동물의 음식점 동반 출입 허용 여부를 논의합니다.",
        "image_url": "https://images.unsplash.com/photo-1587300003388-59208cc962cb?w=800&h=400&fit=crop",
        "category": "사회",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 75700,
        "view_count": 118000,
        "ends_at": now + timedelta(days=15),
        "options": [
            {"text": "전면 허용", "vote_count": 15400},
            {"text": "조건부 허용 (펫존 분리)", "vote_count": 38200},
            {"text": "허용 반대", "vote_count": 22100},
        ],
        "ai_content": """### 반려동물 동반 외식 논란

한국의 반려동물 양육 가구는 2024년 기준 **602만 가구**(전체의 28.2%)로, 반려인구는 약 **1,500만 명**에 달합니다. 그러나 「식품위생법」은 음식점 내 동물 출입을 원칙적으로 금지하고 있어, 반려인과 비반려인 간 갈등이 커지고 있습니다.

### 허용 찬성 입장

반려동물 산업 규모는 **연 6.5조원**으로 급성장 중이며, 펫프렌들리 카페·식당 수요가 폭발적입니다. 프랑스·독일 등 유럽 대부분의 국가는 식당 내 반려동물 동반을 **보편적으로 허용**하고 있으며, 위생 문제 보고율은 **0.3% 미만**입니다. 한국반려동물산업협회는 "반려동물은 가족이며, 사회적 포용이 필요하다"고 주장합니다.

### 반대 입장

식품의약품안전처는 동물 털·비듬이 식품에 혼입될 위험, 알레르기 유발, 위생 관리 어려움 등을 이유로 신중한 입장입니다. 대한의사협회는 "면역력이 약한 영유아·노인이 있는 공간에서 동물 접촉은 위험할 수 있다"고 경고합니다. 실제로 2023년 반려동물 동반 식당 민원 중 **62%가 위생·소음** 관련이었습니다.

### 조건부 허용 모델

서울시가 2024년 시범 도입한 **'펫존 분리제'**가 대안으로 주목받고 있습니다. 별도 공간을 두어 비반려인의 선택권을 보장하면서, 반려인도 외식할 수 있게 하는 방식입니다. 시범 운영 매장 120곳 중 **78%가 매출 증가**를 보고했습니다.""",
        "sources": [
            {"title": "2024 반려동물 보유현황 조사 - 농림축산식품부", "url": "https://www.mafra.go.kr/bbs/mafra/71/325834/artclView.do", "source_type": "NEWS"},
            {"title": "유럽 반려동물 동반 외식 규정 비교", "url": "https://www.efsa.europa.eu/en/topics/topic/animal-welfare", "source_type": "PAPER"},
            {"title": "서울시 펫존 분리제 시범사업 결과 보고서", "url": "https://news.seoul.go.kr/welfare/archives/561234", "source_type": "NEWS"},
        ],
        "comments": [
            {"user_idx": 1, "content": "펫존 분리가 가장 현실적이네요. 선택할 수 있으니까요", "option_idx": 1, "likes": 321},
            {"user_idx": 2, "content": "유럽에서는 너무 자연스러운 일인데 한국은 왜 안 되는 건지", "option_idx": 0, "likes": 154},
            {"user_idx": 3, "content": "알레르기 있는 사람은요? 선택의 여지가 없잖아요", "option_idx": 2, "likes": 198},
        ],
    },

    # ───── 7. 부동산 다주택자 규제 (BINARY) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000007"),
        "user_idx": 1,
        "title": "부동산 다주택자 규제, 강화해야 할까?",
        "description": "주택 시장 안정을 위한 다주택자 규제 수준에 대한 의견을 수렴합니다.",
        "image_url": "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=800&h=400&fit=crop",
        "category": "경제",
        "poll_type": "OFFICIAL",
        "interaction_type": "BINARY",
        "total_votes": 85600,
        "view_count": 156000,
        "ends_at": now + timedelta(days=9),
        "options": [
            {"text": "규제 강화", "vote_count": 51360},
            {"text": "규제 완화", "vote_count": 34240},
        ],
        "ai_content": """### 다주택자 규제 현황

2025년 현재 다주택자에 대한 주요 규제는 ①종합부동산세 중과(2주택 이상 최대 5%) ②양도소득세 중과(최대 75%) ③취득세 중과(3주택 이상 12%) ④대출 제한(LTV 30% 이하)입니다. 2024년 기준 2주택 이상 보유자는 전체 주택 소유자의 **15.8%**(약 236만 명)입니다.

### 규제 강화 입장

경제정의실천시민연합은 "다주택자의 투기적 수요가 집값 상승의 핵심 원인"이라고 주장합니다. KB국민은행 자료에 따르면 서울 아파트 중위 가격은 **11.2억원**으로 중위 가구소득 대비 **PIR 15.7배**에 달합니다. 이는 뉴욕(12.3배)·도쿄(10.1배)를 상회하는 수준으로, "내 집 마련"이 점점 불가능해지고 있습니다.

### 규제 완화 입장

한국부동산원 분석에 따르면 다주택자 중 **63%가 임대사업자**이며, 이들이 전·월세 공급의 상당 부분을 담당합니다. 과도한 규제로 매물이 줄어 오히려 **전세 가격이 상승**하는 역효과가 나타나고 있습니다. 대한건설협회는 "공급 확대와 세제 정상화가 시장 안정의 핵심"이라고 주장합니다.

### 정책 방향

정부는 2025년 '주택시장 정상화 방안'을 통해 일부 규제를 완화(2주택 종부세율 인하, 일시적 2주택 양도세 비과세 기간 확대)하면서도, 3주택 이상에 대한 중과는 유지하는 **선별적 접근**을 취하고 있습니다.""",
        "sources": [
            {"title": "KB주택가격동향 월간 보고서", "url": "https://kbland.kr/webGnb/main/main.do", "source_type": "NEWS"},
            {"title": "다주택자 세제 정책 효과 분석 - 한국조세재정연구원", "url": "https://www.kipf.re.kr/cmm/fms/FileDown.do", "source_type": "PAPER"},
        ],
        "comments": [
            {"user_idx": 0, "content": "PIR 15배면 30년 한 푼도 안 쓰고 모아야 집 산다는 건데...", "option_idx": 0, "likes": 342},
            {"user_idx": 2, "content": "규제하면 매물 잠기고 전세가 올라요. 시장 원리를 무시하면 안됩니다", "option_idx": 1, "likes": 267},
            {"user_idx": 4, "content": "3주택 이상은 중과 유지하고 2주택은 완화하는 게 맞다 봅니다", "option_idx": 1, "likes": 189},
        ],
    },

    # ───── 8. 선거 연령 하향 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000008"),
        "user_idx": 2,
        "title": "지방선거 선거권 연령을 16세로 낮춰야 할까?",
        "description": "청소년 참정권 확대 논의가 본격화되고 있습니다. 선거 연령 하향에 대한 여러분의 의견은?",
        "image_url": "https://images.unsplash.com/photo-1540910419892-4a36d2c3266c?w=800&h=400&fit=crop",
        "category": "정치",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 76600,
        "view_count": 108000,
        "ends_at": now + timedelta(days=20),
        "options": [
            {"text": "16세로 하향 찬성", "vote_count": 19800},
            {"text": "18세 현행 유지", "vote_count": 25100},
            {"text": "하향 반대 (오히려 상향)", "vote_count": 31700},
        ],
        "ai_content": """### 선거 연령 논의 배경

한국은 2019년 공직선거법 개정으로 선거권 연령을 20세에서 **18세**로 낮추었습니다. 이후 교육계·시민단체를 중심으로 지방선거에 한해 **16세로 추가 하향**하자는 논의가 진행 중입니다. 전 세계적으로 16세 선거권을 도입한 국가는 **오스트리아, 스코틀랜드, 브라질** 등 약 15개국입니다.

### 하향 찬성 입장

16세 청소년은 세금을 내고(아르바이트 소득세), 형사 처벌 대상이며, 운전면허 취득이 가능합니다. "의무는 있는데 권리는 없는" 상태가 모순이라는 것이 핵심 논거입니다. 오스트리아는 2007년 16세 선거권 도입 후 청소년 투표율이 **67%**에 달했으며, 비엔나대학 연구에 따르면 16~17세의 정치 참여도와 정치 지식이 **18~21세와 유의미한 차이가 없었습니다**.

### 반대 입장

한국교원단체총연합회는 "학교가 정치화될 우려"를 지적합니다. 16세는 고등학교 1~2학년으로, 교사의 영향력이 큰 교육 현장에서 **편향된 정치 교육** 가능성이 있다는 것입니다. 또한 여론조사에서 30세 이상 응답자의 **61%**가 "판단력이 미성숙"을 이유로 반대했습니다.

### 지방선거 한정 논의

현재 논의는 지방선거(시·도의회, 시장·군수 등)에 한정됩니다. 지역사회 이슈는 청소년의 **생활과 직결**(통학 환경, 학교 예산, 청소년 시설 등)되므로, 국회의원 선거보다 참정권 부여의 정당성이 높다는 주장입니다.""",
        "sources": [
            {"title": "오스트리아 16세 선거권 10년 평가 보고서", "url": "https://www.tandfonline.com/doi/abs/10.1080/13501763.2018.1481484", "source_type": "PAPER"},
            {"title": "청소년 참정권 확대 논의 현황 - 국회입법조사처", "url": "https://www.nars.go.kr/report/view.do?cmsCode=CM0043", "source_type": "NEWS"},
        ],
        "comments": [
            {"user_idx": 3, "content": "세금은 내면서 투표는 못 한다? 모순이죠", "option_idx": 0, "likes": 198},
            {"user_idx": 4, "content": "학교에서 선생님 영향 받아 투표하면 그게 민주주의인가요", "option_idx": 2, "likes": 234},
            {"user_idx": 0, "content": "지방선거 한정이면 찬성할 수 있어요. 통학 문제는 직접 영향이니까", "option_idx": 0, "likes": 145},
        ],
    },

    # ───── 9. 구글맵 (SINGLE_CHOICE) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000009"),
        "user_idx": 3,
        "title": "구글맵 국내 지도 반출 허용해야 할까?",
        "description": "구글의 국내 정밀지도 데이터 해외 반출 허용 여부에 대한 의견을 수렴합니다.",
        "image_url": "https://images.unsplash.com/photo-1569336415962-a4bd9f69cd83?w=800&h=400&fit=crop",
        "category": "기술",
        "poll_type": "OFFICIAL",
        "interaction_type": "SINGLE_CHOICE",
        "total_votes": 77400,
        "view_count": 124000,
        "ends_at": now + timedelta(days=16),
        "options": [
            {"text": "전면 허용", "vote_count": 22100},
            {"text": "조건부 허용 (군사시설 제외)", "vote_count": 35800},
            {"text": "반출 불허", "vote_count": 19500},
        ],
        "ai_content": """### 구글맵 지도 반출 논쟁

한국은 「공간정보의 구축 및 관리에 관한 법률」에 따라 1:5,000 이상 정밀 지도의 국외 반출을 규제하고 있습니다. 구글은 2007년부터 **5차례** 지도 반출을 신청했으나 모두 불허·조건부 허가에 그쳤습니다. 이로 인해 한국은 구글맵의 **상세 내비게이션·스트리트뷰**가 제한적입니다.

### 허용 찬성 입장

IT 업계는 "시대착오적 규제"라고 비판합니다. 위성 기술 발달로 북한도 구글 위성사진으로 **0.5m 해상도**까지 볼 수 있는데, 지도 반출만 막는 것은 실효성이 없다는 주장입니다. 한국무역협회는 구글맵 활용 제한으로 인한 **관광·물류 산업 손실이 연간 약 3.2조원**에 달한다고 추산합니다. 자율주행차 개발에도 정밀 지도가 필수인데, 국내 업체만으로는 글로벌 경쟁력 확보가 어렵습니다.

### 불허 입장

국방부는 **정밀 지형 데이터가 군사 안보에 직결**된다고 강조합니다. 특히 해안선·지하시설·핵심 인프라의 정밀 좌표가 적국에 넘어갈 경우 미사일 조준 등에 악용될 수 있습니다. 한국국방연구원은 "기술적으로 군사시설만 선별 삭제하는 것은 완벽하지 않다"며 원천 차단을 권고합니다.

### 조건부 허용 모델

국토지리정보원이 검토 중인 **'안보 민감 정보 마스킹 후 반출'** 모델이 대안으로 떠오르고 있습니다. 군사시설·핵심 인프라 좌표를 자동 블러 처리한 뒤 반출을 허용하는 방식으로, 일본·독일 등이 유사한 제도를 운용 중입니다.""",
        "sources": [
            {"title": "구글 지도 반출 논쟁의 쟁점과 과제 - KISDI", "url": "https://www.kisdi.re.kr/report/view.do?key=m2101113025888", "source_type": "PAPER"},
            {"title": "자율주행과 정밀지도 규제 현황", "url": "https://www.motie.go.kr/motie/ne/presse/press2/bbs/bbsView.do?bbs_seq_n=166234", "source_type": "NEWS"},
        ],
        "comments": [
            {"user_idx": 0, "content": "위성 사진으로 다 보이는 시대에 지도 반출 막는 게 무슨 의미가 있나요", "option_idx": 0, "likes": 198},
            {"user_idx": 4, "content": "안보는 안보고 편의는 편의. 조건부 허용이 합리적입니다", "option_idx": 1, "likes": 265},
            {"user_idx": 1, "content": "구글에 데이터 넘기면 다시는 못 돌려받습니다. 신중해야 해요", "option_idx": 2, "likes": 143},
        ],
    },

    # ───── 10. 원전 확대 (RANKING) ─────
    {
        "id": uuid.UUID("10000000-0000-4000-a000-000000000010"),
        "user_idx": 4,
        "title": "기후위기 대응, 에너지 정책 우선순위는?",
        "description": "탄소중립 목표 달성을 위한 에너지 정책의 우선순위를 매겨주세요.",
        "image_url": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800&h=400&fit=crop",
        "category": "환경",
        "poll_type": "OFFICIAL",
        "interaction_type": "RANKING",
        "total_votes": 52300,
        "view_count": 98000,
        "ends_at": now + timedelta(days=25),
        "options": [
            {"text": "원전 확대", "vote_count": 18200},
            {"text": "태양광·풍력 확대", "vote_count": 15400},
            {"text": "에너지 효율화·절약", "vote_count": 12100},
            {"text": "수소·SMR 신기술", "vote_count": 6600},
        ],
        "ai_content": """### 한국의 에너지 전환 과제

한국은 **2050 탄소중립**을 선언했으나, 2024년 기준 전체 발전량의 **석탄 32%, LNG 29%, 원전 28%, 재생에너지 9%** 비율로, OECD 국가 중 화석연료 의존도가 높은 편입니다. 연간 CO₂ 배출량은 **약 5.9억톤**으로 세계 10위권입니다.

### 원전 확대 입장

원전은 발전 과정에서 CO₂를 **거의 배출하지 않으며**, 발전단가가 kWh당 약 **60원**으로 태양광(100원)·풍력(90원)보다 저렴합니다. 정부는 2036년까지 원전 비중을 **36.6%**로 확대하는 에너지 기본계획을 수립했습니다. 한국수력원자력에 따르면 APR-1400 등 한국형 원전의 해외 수출 시장도 **30조원 이상** 규모로 전망됩니다.

### 재생에너지 집중 입장

환경단체는 원전의 **방사성 폐기물 처리 비용**이 발전단가에 포함되지 않은 "숨겨진 비용"이라고 지적합니다. 국제재생에너지기구(IRENA)에 따르면 2023년 전 세계 태양광 발전단가는 10년 전 대비 **89% 하락**했으며, 한국의 해상풍력 잠재량은 **약 30GW**로 원전 30기분에 해당합니다.

### SMR과 수소의 가능성

소형모듈원자로(SMR)는 기존 원전의 1/10 규모로 안전성이 높고 입지 제약이 적어 주목받고 있습니다. 한국원자력연구원의 SMART 원자로는 **세계 최초 SMR 표준설계 인가**를 받았습니다. 수소 경제 역시 2030년까지 **연 390만톤 생산** 목표가 설정되어 있으나, 그린수소 생산 비용이 아직 높아 경제성 확보가 과제입니다.""",
        "sources": [
            {"title": "제11차 전력수급기본계획 - 산업통상자원부", "url": "https://www.motie.go.kr/motie/ne/presse/press2/bbs/bbsView.do?bbs_seq_n=167890", "source_type": "NEWS"},
            {"title": "IRENA Renewable Power Generation Costs 2023", "url": "https://www.irena.org/publications/2024/Jan/Renewable-Power-Generation-Costs-in-2023", "source_type": "PAPER"},
            {"title": "SMART 원자로 해외 수출 전략", "url": "https://www.kaeri.re.kr/board/view?menuId=MENU00476&boardId=BOARD00002", "source_type": "NEWS"},
        ],
        "comments": [
            {"user_idx": 0, "content": "원전이 현실적으로 가장 효율적인 대안이라고 봅니다", "option_idx": 0, "likes": 187},
            {"user_idx": 1, "content": "태양광 단가가 89% 떨어졌는데 아직도 원전만 고집하나요", "option_idx": 1, "likes": 167},
            {"user_idx": 2, "content": "SMR이 미래 기술이긴 한데 아직 상용화 전이라...", "option_idx": 3, "likes": 89},
        ],
    },
]


async def seed(session: AsyncSession) -> None:
    # ────── 1. Nuke all existing data ──────
    print("Clearing existing data...")
    await session.execute(text("DELETE FROM poll_sources"))
    await session.execute(text("DELETE FROM poll_comments"))
    await session.execute(text("DELETE FROM votes"))
    await session.execute(text("DELETE FROM poll_options"))
    await session.execute(text("DELETE FROM polls"))
    # Keep users but clean up demo users
    for u in USERS:
        await session.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": u["id"]})

    # ────── 2. Create users ──────
    for u in USERS:
        await session.execute(
            text("""
                INSERT INTO users (id, name, email, role, created_at, updated_at)
                VALUES (:id, :name, :email, 'USER', NOW(), NOW())
                ON CONFLICT (id) DO NOTHING
            """),
            u,
        )
    print(f"  Created {len(USERS)} users")

    # ────── 3. Create polls ──────
    for poll in POLLS:
        user_id = USERS[poll["user_idx"]]["id"]

        # Insert poll
        await session.execute(
            text("""
                INSERT INTO polls
                    (id, user_id, title, description, image_url, category,
                     type, status, interaction_type, total_votes, view_count,
                     ai_content, ai_updated_at,
                     ends_at, created_at, updated_at, is_deleted)
                VALUES
                    (:id, :user_id, :title, :description, :image_url, :category,
                     :type, 'ACTIVE', :interaction_type, :total_votes, :view_count,
                     :ai_content, :ai_updated_at,
                     :ends_at, NOW(), NOW(), false)
            """),
            {
                "id": poll["id"],
                "user_id": user_id,
                "title": poll["title"],
                "description": poll["description"],
                "image_url": poll.get("image_url"),
                "category": poll["category"],
                "type": poll["poll_type"],
                "interaction_type": poll["interaction_type"],
                "total_votes": poll["total_votes"],
                "view_count": poll["view_count"],
                "ai_content": poll.get("ai_content"),
                "ai_updated_at": now if poll.get("ai_content") else None,
                "ends_at": poll["ends_at"],
            },
        )

        # Insert options
        option_ids = []
        for i, opt in enumerate(poll["options"]):
            opt_id = uuid.uuid4()
            option_ids.append(opt_id)
            await session.execute(
                text("""
                    INSERT INTO poll_options (id, poll_id, text, "order", vote_count)
                    VALUES (:id, :poll_id, :text, :ord, :vote_count)
                """),
                {
                    "id": opt_id,
                    "poll_id": poll["id"],
                    "text": opt["text"],
                    "ord": i,
                    "vote_count": opt.get("vote_count", 0),
                },
            )

        # Insert sources
        for src in poll.get("sources", []):
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

        # Insert comments
        for c in poll.get("comments", []):
            comment_user_id = USERS[c["user_idx"]]["id"]
            option_id = option_ids[c["option_idx"]] if "option_idx" in c else None
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
                    "id": uuid.uuid4(),
                    "poll_id": poll["id"],
                    "user_id": comment_user_id,
                    "content": c["content"],
                    "option_id": option_id,
                    "likes": c.get("likes", 0),
                },
            )

        src_count = len(poll.get("sources", []))
        cmt_count = len(poll.get("comments", []))
        print(f"  ✓ {poll['title']} ({len(poll['options'])} opts, {src_count} srcs, {cmt_count} cmts)")

    await session.commit()
    print(f"\n✅ Seeded: {len(POLLS)} polls with AI content, sources, and comments")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        await seed(session)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
