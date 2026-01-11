"""
Evidence checker using NLI model.

Determines if evidence supports, refutes, or is neutral to a claim.
"""

import logging

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.services.verification.stage2_rag.models import Evidence, EvidenceCheckResult

logger = logging.getLogger(__name__)


class EvidenceChecker:
    """
    Check claims against evidence using Natural Language Inference.

    Uses DeBERTa-v3 fine-tuned on NLI tasks.
    Labels: 0=CONTRADICTION, 1=NEUTRAL, 2=ENTAILMENT
    """

    # Default model - good balance of speed and accuracy
    DEFAULT_MODEL = "cross-encoder/nli-deberta-v3-small"
    # Alternative: "cross-encoder/nli-deberta-v3-base" for higher accuracy

    _instance = None
    _model = None
    _tokenizer = None

    def __new__(cls, model_name: str | None = None):
        """Singleton pattern to avoid loading model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str | None = None):
        if self._initialized:
            return

        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._load_model()
        self._initialized = True

    def _load_model(self):
        """Load the NLI model and tokenizer."""
        logger.info(f"Loading NLI model: {self.model_name}")
        try:
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name
            )
            self._model.to(self.device)
            self._model.eval()
            logger.info(f"NLI model loaded on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load NLI model: {e}")
            raise

    def check(self, claim: str, evidence: Evidence) -> EvidenceCheckResult:
        """
        Check if evidence supports, refutes, or is neutral to the claim.

        Args:
            claim: The claim to verify
            evidence: Evidence to check against

        Returns:
            EvidenceCheckResult with scores and verdict
        """
        if not evidence.text:
            return EvidenceCheckResult(
                evidence=evidence,
                entailment_score=0.0,
                contradiction_score=0.0,
                neutral_score=1.0,
                verdict="NEUTRAL",
            )

        try:
            # Prepare input: premise (evidence) + hypothesis (claim)
            inputs = self._tokenizer(
                evidence.text,  # premise
                claim,  # hypothesis
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True,
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get predictions
            with torch.no_grad():
                outputs = self._model(**inputs)
                probs = torch.softmax(outputs.logits, dim=-1)[0]

            # Extract scores (order: contradiction, neutral, entailment)
            contradiction_score = probs[0].item()
            neutral_score = probs[1].item()
            entailment_score = probs[2].item()

            # Determine verdict
            max_score = max(contradiction_score, neutral_score, entailment_score)
            if max_score == entailment_score and entailment_score > 0.5:
                verdict = "SUPPORTS"
            elif max_score == contradiction_score and contradiction_score > 0.5:
                verdict = "REFUTES"
            else:
                verdict = "NEUTRAL"

            return EvidenceCheckResult(
                evidence=evidence,
                entailment_score=entailment_score,
                contradiction_score=contradiction_score,
                neutral_score=neutral_score,
                verdict=verdict,
            )

        except Exception as e:
            logger.error(f"Error checking evidence: {e}")
            return EvidenceCheckResult(
                evidence=evidence,
                entailment_score=0.0,
                contradiction_score=0.0,
                neutral_score=1.0,
                verdict="NEUTRAL",
            )

    def check_batch(
        self, claim: str, evidences: list[Evidence]
    ) -> list[EvidenceCheckResult]:
        """Check multiple evidences against a claim."""
        return [self.check(claim, evidence) for evidence in evidences]
