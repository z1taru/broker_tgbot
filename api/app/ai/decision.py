# api/app/ai/decision.py
from typing import List, Optional, Tuple
from app.models.database import FAQ
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DecisionEngine:
    def __init__(self):
        self.high_threshold = settings.AI_SIMILARITY_THRESHOLD_HIGH
        self.low_threshold = settings.AI_SIMILARITY_THRESHOLD_LOW
    
    def make_decision(
        self,
        faqs_with_scores: List[Tuple[FAQ, float]]
    ) -> dict:
        """
        Decide action based on similarity scores
        
        Returns:
            dict with keys: action, faq (optional), score, all_matches
        """
        if not faqs_with_scores:
            return {
                "action": "no_match",
                "score": 0.0,
                "all_matches": []
            }
        
        best_faq, best_score = faqs_with_scores[0]
        
        if best_score >= self.high_threshold:
            logger.info(f"High confidence match: {best_score:.3f}")
            return {
                "action": "direct_answer",
                "faq": best_faq,
                "score": best_score,
                "all_matches": faqs_with_scores
            }
        
        elif best_score >= self.low_threshold:
            logger.info(f"Medium confidence match: {best_score:.3f}")
            return {
                "action": "clarify",
                "faq": best_faq,
                "score": best_score,
                "all_matches": faqs_with_scores[:3]
            }
        
        else:
            logger.info(f"Low confidence match: {best_score:.3f}")
            return {
                "action": "no_match",
                "score": best_score,
                "all_matches": faqs_with_scores
            }