"""
Zero-shot 분류기 - 국제 정세 이벤트 분류

facebook/bart-large-mnli 모델을 사용하여 텍스트를 국제 정세 관련 여부로 분류.
LLM 호출 전에 사용하여 비용 절감 및 속도 향상.

Pipeline:
1. Rule-based exclusion (fast, free)
2. Zero-shot classification (local model) ← 이 모듈
3. LLM verification (edge cases only)
"""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

# Lazy loading to avoid import overhead
_classifier = None
_model_loaded = False


# ============================================
# 분류 레이블 정의 (CAMEO/ACLED 기반)
# ============================================

# 국제 정세 레이블 (통과)
INTERNATIONAL_AFFAIRS_LABELS = [
    "military conflict",
    "diplomatic relations",
    "political crisis",
    "terrorism",
    "humanitarian crisis",
    "international sanctions",
    "protest and civil unrest",
]

# 비국제 정세 레이블 (거부)
REJECT_LABELS = [
    "sports",
    "entertainment",
    "local news",
    "opinion and analysis",
    "advertisement",
]


class ZeroShotClassifier:
    """Zero-shot 분류기 클래스"""

    def __init__(self, model_name: str = "facebook/bart-large-mnli"):
        """
        Args:
            model_name: HuggingFace 모델 이름
        """
        self.model_name = model_name
        self._pipeline = None
        self.intl_labels = INTERNATIONAL_AFFAIRS_LABELS
        self.reject_labels = REJECT_LABELS

    def _load_model(self):
        """지연 로딩으로 모델 초기화"""
        if self._pipeline is None:
            try:
                from transformers import pipeline
                logger.info(f"Loading zero-shot classifier: {self.model_name}")
                self._pipeline = pipeline(
                    "zero-shot-classification",
                    model=self.model_name,
                    device=-1,  # CPU 사용 (-1), GPU 사용시 0
                )
                logger.info("Zero-shot classifier loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load zero-shot classifier: {e}")
                raise

    def classify(self, text: str) -> tuple[bool, float, str]:
        """
        텍스트를 국제 정세 관련 여부로 분류

        Args:
            text: 분류할 텍스트 (최대 512자로 truncate)

        Returns:
            (is_international, confidence, top_label)
            - is_international: 국제 정세 관련 여부
            - confidence: 신뢰도 (0-1)
            - top_label: 가장 높은 확률의 레이블
        """
        self._load_model()

        # 텍스트 길이 제한 (BART 토큰 제한)
        truncated_text = text[:512]

        all_labels = self.intl_labels + self.reject_labels

        try:
            result = self._pipeline(truncated_text, all_labels)

            top_label = result["labels"][0]
            confidence = result["scores"][0]

            is_intl = top_label in self.intl_labels

            logger.debug(
                f"[ZERO-SHOT] '{text[:50]}...' → {top_label} ({confidence:.2f})"
            )

            return is_intl, confidence, top_label

        except Exception as e:
            logger.warning(f"Zero-shot classification error: {e}")
            # 에러 시 통과 (LLM이 최종 검증)
            return True, 0.5, "ERROR"

    def classify_batch(self, texts: list[str]) -> list[tuple[bool, float, str]]:
        """
        배치 분류

        Args:
            texts: 분류할 텍스트 목록

        Returns:
            [(is_international, confidence, top_label), ...]
        """
        return [self.classify(text) for text in texts]


# ============================================
# 전역 인스턴스 (Singleton)
# ============================================

_zero_shot_instance: ZeroShotClassifier | None = None


def get_zero_shot_classifier() -> ZeroShotClassifier:
    """
    Zero-shot 분류기 싱글톤 인스턴스 반환

    Returns:
        ZeroShotClassifier 인스턴스
    """
    global _zero_shot_instance
    if _zero_shot_instance is None:
        _zero_shot_instance = ZeroShotClassifier()
    return _zero_shot_instance


# ============================================
# 테스트
# ============================================

if __name__ == "__main__":
    # 테스트 케이스
    test_texts = [
        "Iran attacks US bases in Iraq, 3 soldiers injured",
        "TikTok deal between China and White House finalized",
        "World Cup final: France defeats Argentina 3-2",
        "Putin meets Trump envoys as Kremlin says Ukraine settlement hinges on territory",
        "Judge warns Trump administration on immigration status",
        "손흥민이 토트넘에서 해트트릭 기록",
    ]

    classifier = get_zero_shot_classifier()

    print("\n" + "=" * 70)
    print("ZERO-SHOT CLASSIFIER TEST")
    print("=" * 70)

    for text in test_texts:
        is_intl, conf, label = classifier.classify(text)
        status = "PASS" if is_intl else "REJECT"
        print(f"\n[{status}] {label} ({conf:.2f})")
        print(f"  Text: {text[:60]}...")
