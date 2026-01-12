"""
Anomaly Detection 레이어

키워드 매칭과 별개로 "정보 흐름의 변화"를 감지
- 볼륨 스파이크: 평소보다 갑자기 많은 이벤트
- 속도 변화: 특정 토픽의 언급 빈도 급증
- 새로운 패턴: 기존 baseline과 다른 분포

장점:
- 키워드에 없는 새로운 유형의 사건 감지
- 암호화된 언어, 신조어도 볼륨으로 감지
- 연구 결과: AUC 86.6% ~ 93.7%
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AnomalySignal:
    """이상 신호 정보"""
    signal_type: str          # volume_spike, velocity_change, distribution_shift
    severity: float           # 0.0 ~ 1.0
    z_score: float            # 표준편차 기준 얼마나 벗어났는지
    baseline_value: float     # 평소 값
    current_value: float      # 현재 값
    detected_at: datetime
    description: str
    metadata: dict = field(default_factory=dict)


class AnomalyDetector:
    """
    시계열 이상 감지기

    EWMA (Exponentially Weighted Moving Average) + Z-Score 기반
    - 짧은 윈도우: 급격한 스파이크 감지
    - 긴 윈도우: 점진적 변화 감지
    """

    def __init__(
        self,
        short_window: int = 10,      # 최근 10개 샘플
        long_window: int = 100,       # 최근 100개 샘플
        z_threshold: float = 3.0,     # 3 시그마 기준
        min_samples: int = 5,         # 최소 샘플 수
    ):
        self.short_window = short_window
        self.long_window = long_window
        self.z_threshold = z_threshold
        self.min_samples = min_samples

        # 볼륨 추적 (스캔당 이벤트 수)
        self.volume_history: deque[tuple[datetime, int]] = deque(maxlen=long_window)

        # 소스별 볼륨 추적
        self.source_volumes: dict[str, deque[tuple[datetime, int]]] = {}

        # 키워드별 빈도 추적
        self.keyword_frequencies: dict[str, deque[tuple[datetime, int]]] = {}

        # EWMA 상태
        self._ewma_short: float | None = None
        self._ewma_long: float | None = None
        self._ewma_alpha_short = 2 / (short_window + 1)
        self._ewma_alpha_long = 2 / (long_window + 1)

    def record_scan(
        self,
        event_count: int,
        source_counts: dict[str, int] | None = None,
        keyword_counts: dict[str, int] | None = None,
        timestamp: datetime | None = None,
    ) -> list[AnomalySignal]:
        """
        스캔 결과 기록 및 이상 감지

        Args:
            event_count: 이번 스캔에서 감지된 총 이벤트 수
            source_counts: 소스별 이벤트 수 {"gdelt": 10, "twitter": 5}
            keyword_counts: 키워드별 매칭 수 {"war": 3, "protest": 7}
            timestamp: 스캔 시간 (기본: 현재)

        Returns:
            감지된 이상 신호 목록
        """
        timestamp = timestamp or datetime.utcnow()
        anomalies = []

        # 1. 전체 볼륨 체크
        self.volume_history.append((timestamp, event_count))
        volume_anomaly = self._check_volume_anomaly(event_count, timestamp)
        if volume_anomaly:
            anomalies.append(volume_anomaly)

        # 2. 소스별 볼륨 체크
        if source_counts:
            for source, count in source_counts.items():
                if source not in self.source_volumes:
                    self.source_volumes[source] = deque(maxlen=self.long_window)
                self.source_volumes[source].append((timestamp, count))

                source_anomaly = self._check_source_anomaly(source, count, timestamp)
                if source_anomaly:
                    anomalies.append(source_anomaly)

        # 3. 키워드별 빈도 체크
        if keyword_counts:
            for keyword, count in keyword_counts.items():
                if keyword not in self.keyword_frequencies:
                    self.keyword_frequencies[keyword] = deque(maxlen=self.long_window)
                self.keyword_frequencies[keyword].append((timestamp, count))

                keyword_anomaly = self._check_keyword_anomaly(keyword, count, timestamp)
                if keyword_anomaly:
                    anomalies.append(keyword_anomaly)

        # EWMA 업데이트
        self._update_ewma(event_count)

        if anomalies:
            logger.warning(f"Anomaly detected: {len(anomalies)} signals")
            for a in anomalies:
                logger.warning(f"  - {a.signal_type}: {a.description} (z={a.z_score:.2f})")

        return anomalies

    def _check_volume_anomaly(
        self, current: int, timestamp: datetime
    ) -> AnomalySignal | None:
        """전체 볼륨 이상 체크"""
        if len(self.volume_history) < self.min_samples:
            return None

        values = [v for _, v in self.volume_history]
        mean = np.mean(values[:-1])  # 현재 값 제외
        std = np.std(values[:-1])

        if std == 0:
            return None

        z_score = (current - mean) / std

        if abs(z_score) >= self.z_threshold:
            severity = min(1.0, abs(z_score) / (self.z_threshold * 2))
            return AnomalySignal(
                signal_type="volume_spike" if z_score > 0 else "volume_drop",
                severity=severity,
                z_score=z_score,
                baseline_value=mean,
                current_value=current,
                detected_at=timestamp,
                description=f"Event volume {current} is {abs(z_score):.1f}σ from baseline {mean:.1f}",
                metadata={"history_length": len(values)},
            )

        return None

    def _check_source_anomaly(
        self, source: str, current: int, timestamp: datetime
    ) -> AnomalySignal | None:
        """소스별 이상 체크"""
        history = self.source_volumes.get(source, [])
        if len(history) < self.min_samples:
            return None

        values = [v for _, v in history]
        mean = np.mean(values[:-1])
        std = np.std(values[:-1])

        if std == 0:
            return None

        z_score = (current - mean) / std

        if abs(z_score) >= self.z_threshold:
            severity = min(1.0, abs(z_score) / (self.z_threshold * 2))
            return AnomalySignal(
                signal_type=f"source_spike:{source}",
                severity=severity,
                z_score=z_score,
                baseline_value=mean,
                current_value=current,
                detected_at=timestamp,
                description=f"{source} volume {current} is {abs(z_score):.1f}σ from baseline {mean:.1f}",
                metadata={"source": source},
            )

        return None

    def _check_keyword_anomaly(
        self, keyword: str, current: int, timestamp: datetime
    ) -> AnomalySignal | None:
        """키워드별 이상 체크"""
        history = self.keyword_frequencies.get(keyword, [])
        if len(history) < self.min_samples:
            return None

        values = [v for _, v in history]
        mean = np.mean(values[:-1])
        std = np.std(values[:-1])

        if std == 0:
            # 표준편차 0이지만 현재 값이 평균보다 훨씬 크면 이상
            if current > mean * 3 and current >= 3:
                return AnomalySignal(
                    signal_type=f"keyword_spike:{keyword}",
                    severity=0.8,
                    z_score=float("inf"),
                    baseline_value=mean,
                    current_value=current,
                    detected_at=timestamp,
                    description=f"'{keyword}' frequency {current} >> baseline {mean:.1f}",
                    metadata={"keyword": keyword},
                )
            return None

        z_score = (current - mean) / std

        if z_score >= self.z_threshold:  # 키워드는 증가만 체크
            severity = min(1.0, z_score / (self.z_threshold * 2))
            return AnomalySignal(
                signal_type=f"keyword_spike:{keyword}",
                severity=severity,
                z_score=z_score,
                baseline_value=mean,
                current_value=current,
                detected_at=timestamp,
                description=f"'{keyword}' frequency {current} is {z_score:.1f}σ above baseline {mean:.1f}",
                metadata={"keyword": keyword},
            )

        return None

    def _update_ewma(self, value: int):
        """EWMA 업데이트"""
        if self._ewma_short is None:
            self._ewma_short = float(value)
            self._ewma_long = float(value)
        else:
            self._ewma_short = (
                self._ewma_alpha_short * value +
                (1 - self._ewma_alpha_short) * self._ewma_short
            )
            self._ewma_long = (
                self._ewma_alpha_long * value +
                (1 - self._ewma_alpha_long) * self._ewma_long
            )

    def get_ewma_divergence(self) -> float | None:
        """
        단기/장기 EWMA 괴리율 반환

        양수: 단기가 장기보다 높음 (상승 추세)
        음수: 단기가 장기보다 낮음 (하락 추세)
        """
        if self._ewma_short is None or self._ewma_long is None:
            return None
        if self._ewma_long == 0:
            return None
        return (self._ewma_short - self._ewma_long) / self._ewma_long

    def get_status(self) -> dict:
        """현재 상태 반환"""
        return {
            "volume_samples": len(self.volume_history),
            "sources_tracked": list(self.source_volumes.keys()),
            "keywords_tracked": list(self.keyword_frequencies.keys()),
            "ewma_short": self._ewma_short,
            "ewma_long": self._ewma_long,
            "ewma_divergence": self.get_ewma_divergence(),
        }

    def reset(self):
        """상태 초기화"""
        self.volume_history.clear()
        self.source_volumes.clear()
        self.keyword_frequencies.clear()
        self._ewma_short = None
        self._ewma_long = None
