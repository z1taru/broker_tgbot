# api/app/ai/decision.py
from typing import List, Tuple, Dict, Any
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DecisionEngine:
    def __init__(self):
        self.vector_threshold = 0.55
        self.keyword_threshold = 0.35
        self.low_threshold = 0.20
    
    def make_decision(
        self,
        faqs_with_scores: List[Tuple[Dict[str, Any], float]],
        user_question: str = ""
    ) -> dict:
        """
        Принятие решения на основе найденных FAQ
        
        ЛОГИКА:
        - Если FAQ найдены → ВСЕГДА отдавать лучший результат
        - GPT только если список пустой
        - score >= 0.55 → direct_answer
        - score 0.35-0.55 → direct_answer с suggestions
        - score 0.20-0.35 → show_similar
        - score < 0.20 → no_match
        """
        if not faqs_with_scores:
            return {
                "action": "no_match",
                "score": 0.0,
                "all_matches": [],
                "message": "no_results"
            }
        
        best_faq, best_score = faqs_with_scores[0]
        
        # 1. HIGH confidence (≥55%) → ПРЯМОЙ ОТВЕТ
        if best_score >= self.vector_threshold:
            logger.info(f"✅ HIGH confidence: {best_score:.3f}")
            return {
                "action": "direct_answer",
                "faq": best_faq,
                "score": best_score,
                "all_matches": faqs_with_scores
            }
        
        # 2. MEDIUM confidence (35-55%) → ПРЯМОЙ ОТВЕТ + suggestions
        elif best_score >= self.keyword_threshold:
            close_matches = [
                (faq, score) for faq, score in faqs_with_scores[:5]
                if score >= self.keyword_threshold * 0.85
            ]
            
            if len(close_matches) >= 2:
                logger.info(f"🤔 MEDIUM confidence with {len(close_matches)} close matches: {best_score:.3f}")
                return {
                    "action": "clarify",
                    "faq": best_faq,
                    "score": best_score,
                    "all_matches": close_matches[:3],
                    "message": "multiple_options"
                }
            else:
                logger.info(f"✅ MEDIUM confidence, single match: {best_score:.3f}")
                return {
                    "action": "direct_answer",
                    "faq": best_faq,
                    "score": best_score,
                    "all_matches": faqs_with_scores,
                    "message": "single_medium_match"
                }
        
        # 3. LOW confidence (20-35%) → показать похожие
        elif best_score >= self.low_threshold:
            logger.info(f"📋 LOW confidence, showing similar: {best_score:.3f}")
            similar = [
                (faq, score) for faq, score in faqs_with_scores[:5]
                if score >= self.low_threshold
            ]
            return {
                "action": "show_similar",
                "faq": best_faq,
                "score": best_score,
                "all_matches": similar,
                "message": "similar_questions"
            }
        
        # 4. VERY LOW (<20%) → no match
        else:
            logger.info(f"❌ Very LOW confidence: {best_score:.3f}")
            return {
                "action": "no_match",
                "score": best_score,
                "all_matches": faqs_with_scores[:3],
                "message": "no_match_found"
            }