"""
X/Twitter 트리거 - Twikit 기반 (개인 계정 사용)

특징:
- 무료 (공식 API 키 불필요)
- 개인 계정 쿠키로 인증
- 실시간 글로벌 검색
- ToS 위반 위험 있음 (부계정 권장)

설정 필요:
- X_USERNAME: X/Twitter 사용자명
- X_EMAIL: X/Twitter 이메일
- X_PASSWORD: X/Twitter 비밀번호
- X_COOKIES_PATH: 쿠키 저장 경로 (선택)
"""

import hashlib
import logging
from datetime import datetime
from pathlib import Path

from .base import BaseTrigger, TriggerEvent, TriggerSource

logger = logging.getLogger(__name__)


class TwitterTrigger(BaseTrigger):
    """
    X/Twitter 트리거 (Twikit 라이브러리 사용)

    개인 계정으로 로그인하여 트윗 검색
    공식 API 키 불필요 - 브라우저처럼 작동
    """

    def __init__(
        self,
        username: str | None = None,
        email: str | None = None,
        password: str | None = None,
        cookies_path: str | None = None,
        keywords: list[str] | None = None,
        max_results: int = 30,
    ):
        super().__init__(keywords)
        self.username = username
        self.email = email
        self.password = password
        self.cookies_path = cookies_path
        self.max_results = max_results
        self.client = None
        self.seen_tweet_ids: set[str] = set()

    @property
    def source_type(self) -> TriggerSource:
        return TriggerSource.TWITTER

    @property
    def source_name(self) -> str:
        return "X/Twitter"

    async def initialize(self) -> bool:
        """
        Twikit 클라이언트 초기화 및 로그인

        쿠키가 있으면 재사용, 없으면 로그인 후 저장
        """
        try:
            from twikit import Client

            self.client = Client('en-US')

            # 쿠키 파일이 있으면 로드
            if self.cookies_path and Path(self.cookies_path).exists():
                self.client.load_cookies(self.cookies_path)
                logger.info("X/Twitter: Loaded cookies from file")
                self.is_initialized = True
                return True

            # 쿠키 없으면 로그인
            if self.username and self.password:
                await self.client.login(
                    auth_info_1=self.username,
                    auth_info_2=self.email,
                    password=self.password,
                )
                logger.info("X/Twitter: Logged in successfully")

                # 쿠키 저장 (다음에 재사용)
                if self.cookies_path:
                    self.client.save_cookies(self.cookies_path)
                    logger.info(f"X/Twitter: Cookies saved to {self.cookies_path}")

                self.is_initialized = True
                return True

            logger.warning("X/Twitter: No credentials provided")
            return False

        except ImportError:
            logger.error("X/Twitter: twikit not installed. Run: pip install twikit")
            return False
        except Exception as e:
            logger.error(f"X/Twitter initialization error: {e}")
            return False

    async def scan(self) -> list[TriggerEvent]:
        """X/Twitter에서 키워드 검색"""
        if not self.is_initialized or not self.client:
            logger.warning("X/Twitter: Not initialized, skipping scan")
            return []

        self.last_scan = datetime.utcnow()
        events = []

        # 키워드를 OR로 조합
        query = " OR ".join(self.keywords[:10])

        try:
            # Latest 탭에서 검색 (실시간)
            tweets = await self.client.search_tweet(query, 'Latest', count=self.max_results)

            for tweet in tweets:
                tweet_id = str(tweet.id)

                # 중복 체크
                if tweet_id in self.seen_tweet_ids:
                    continue
                self.seen_tweet_ids.add(tweet_id)

                # 키워드 매칭 확인
                text = tweet.text or ""
                matched = self._matches_keywords(text)

                if matched:
                    # 미디어 URL 추출
                    media_urls = []
                    if hasattr(tweet, 'media') and tweet.media:
                        for m in tweet.media:
                            if hasattr(m, 'media_url_https'):
                                media_urls.append(m.media_url_https)

                    events.append(TriggerEvent(
                        title=text[:200],
                        source=TriggerSource.TWITTER,
                        source_name=f"@{tweet.user.screen_name}" if tweet.user else "unknown",
                        url=f"https://x.com/{tweet.user.screen_name}/status/{tweet_id}" if tweet.user else "",
                        detected_at=datetime.utcnow(),
                        content=text,
                        author=tweet.user.screen_name if tweet.user else "",
                        keywords_matched=matched,
                        media_urls=media_urls,
                        engagement={
                            "likes": getattr(tweet, 'favorite_count', 0),
                            "retweets": getattr(tweet, 'retweet_count', 0),
                            "replies": getattr(tweet, 'reply_count', 0),
                        },
                        raw_data={
                            "id": tweet_id,
                            "created_at": str(getattr(tweet, 'created_at', '')),
                        },
                    ))

            # 메모리 관리
            if len(self.seen_tweet_ids) > 5000:
                self.seen_tweet_ids.clear()

            logger.info(f"X/Twitter scan: {len(tweets) if tweets else 0} tweets, {len(events)} matched")

        except Exception as e:
            logger.error(f"X/Twitter scan error: {e}")
            # 인증 만료 시 재초기화 시도
            if "401" in str(e) or "403" in str(e):
                logger.warning("X/Twitter: Auth expired, re-initializing...")
                self.is_initialized = False

        return events

    async def close(self):
        """리소스 정리"""
        self.seen_tweet_ids.clear()
        if self.client and self.cookies_path:
            try:
                self.client.save_cookies(self.cookies_path)
            except:
                pass
        self.client = None
