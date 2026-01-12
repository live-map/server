"""
자율 조사 에이전트 실행 스크립트

사용법:
    # 1회 스캔 + 조사
    python -m app.agents.main --once

    # 15분 주기 스캐너 실행
    python -m app.agents.main --scheduler

    # 특정 사건 수동 조사
    python -m app.agents.main --investigate "Protests in Tehran, Iran"
"""

import argparse
import asyncio
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import agent_settings
from .investigator import InvestigationAgent
from .scanner import NewsScanner

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class AgentRunner:
    """에이전트 실행기"""

    def __init__(self):
        self.scanner = NewsScanner(on_event_detected=self._on_event)
        self.investigator = InvestigationAgent()
        self.scheduler = AsyncIOScheduler()
        self.investigation_queue: list[tuple[str, str]] = []
        self.is_investigating = False

    async def _on_event(self, description: str, category: str):
        """사건 감지 시 콜백"""
        logger.info(f"🚨 Event detected: {description} [{category}]")
        self.investigation_queue.append((description, category))

        # 조사 중이 아니면 시작
        if not self.is_investigating:
            await self._process_queue()

    async def _process_queue(self):
        """조사 큐 처리"""
        while self.investigation_queue:
            self.is_investigating = True
            event, category = self.investigation_queue.pop(0)

            logger.info(f"🔍 Starting investigation: {event}")
            try:
                report = await self.investigator.investigate(event, category)
                self._print_report(report)
            except Exception as e:
                logger.error(f"Investigation error: {e}")

        self.is_investigating = False

    def _print_report(self, report):
        """리포트 출력"""
        print("\n" + "=" * 70)
        print("📋 INVESTIGATION REPORT")
        print("=" * 70)
        print(f"⏰ Generated: {report.generated_at}")
        print(f"\n📝 Summary:\n   {report.event_summary}")
        print(f"\n📍 Location: {report.location or 'Unknown'}")
        print(f"🏷️ Category: {report.category}")

        if report.timeline:
            print(f"\n⏱️ Timeline:")
            for item in report.timeline:
                print(f"   • {item}")

        if report.verified_facts:
            print(f"\n✅ Verified Facts ({len(report.verified_facts)}):")
            for fact in report.verified_facts:
                claim = fact.get("claim", str(fact))
                conf = fact.get("confidence", 0)
                sources = fact.get("supporting_sources", [])
                print(f"   • {claim}")
                print(f"     Confidence: {conf:.0%} | Sources: {', '.join(sources)}")

        if report.unverified_claims:
            print(f"\n⚠️ Unverified Claims:")
            for claim in report.unverified_claims:
                print(f"   • {claim}")

        print(f"\n📰 Sources Used: {', '.join(report.sources) or 'None'}")
        print(f"🎬 Media Collected: {len(report.media)} items")
        print("=" * 70 + "\n")

    async def run_once(self):
        """1회 스캔 + 조사"""
        logger.info("Running single scan...")
        events = await self.scanner.scan()

        if events:
            logger.info(f"Found {len(events)} events, starting investigations...")
            await self._process_queue()
        else:
            logger.info("No significant events found.")

    async def run_scheduler(self):
        """주기적 스캔 실행"""
        logger.info(
            f"Starting scheduler (interval: {agent_settings.scan_interval_minutes} min)"
        )

        # 즉시 1회 실행
        await self.run_once()

        # 스케줄러 설정
        self.scheduler.add_job(
            self.run_once,
            "interval",
            minutes=agent_settings.scan_interval_minutes,
            id="news_scanner",
        )

        self.scheduler.start()

        # 무한 대기
        try:
            while True:
                await asyncio.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown()

    async def investigate_manual(self, event: str, category: str = "other"):
        """수동 조사"""
        logger.info(f"Manual investigation: {event}")
        report = await self.investigator.investigate(event, category)
        self._print_report(report)
        return report


async def main():
    parser = argparse.ArgumentParser(description="Autonomous Investigation Agent")
    parser.add_argument("--once", action="store_true", help="Run single scan")
    parser.add_argument(
        "--scheduler", action="store_true", help="Run with scheduler (15min interval)"
    )
    parser.add_argument("--investigate", type=str, help="Manually investigate an event")
    parser.add_argument(
        "--category",
        type=str,
        default="other",
        help="Event category for manual investigation",
    )

    args = parser.parse_args()

    runner = AgentRunner()

    if args.investigate:
        await runner.investigate_manual(args.investigate, args.category)
    elif args.scheduler:
        await runner.run_scheduler()
    elif args.once:
        await runner.run_once()
    else:
        # 기본: 1회 실행
        await runner.run_once()


if __name__ == "__main__":
    asyncio.run(main())
