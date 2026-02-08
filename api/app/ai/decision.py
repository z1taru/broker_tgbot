from typing import List, Tuple, Dict, Any
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DecisionEngine:
    def __init__(self):
        # НОВЫЕ ПОРОГИ - более гибкие
        self.high_threshold = 0.55  # было 0.7 → теперь 0.55 (55%)
        self.medium_threshold = 0.35  # было 0.3 → теперь 0.35 (35%)
        self.low_threshold = 0.20  # новый порог для "возможно релевантно"
    
    def make_decision(
        self,
        faqs_with_scores: List[Tuple[Dict[str, Any], float]],
        user_question: str = ""
    ) -> dict:
        """
        Умное принятие решения на основе similarity scores
        
        ЛОГИКА:
        - score >= 0.55 (55%) → ПРЯМОЙ ОТВЕТ
        - score 0.35-0.55 (35-55%) → УТОЧНЯЮЩИЙ ВОПРОС (если есть близкие варианты)
        - score 0.20-0.35 (20-35%) → ПОКАЗАТЬ ПОХОЖИЕ (не GPT-вопрос!)
        - score < 0.20 (< 20%) → НЕТ ОТВЕТА
        """
        if not faqs_with_scores:
            return {
                "action": "no_match",
                "score": 0.0,
                "all_matches": [],
                "message": "no_results"
            }
        
        best_faq, best_score = faqs_with_scores[0]
        
        # 1. ПРЯМОЙ ОТВЕТ (≥55%)
        if best_score >= self.high_threshold:
            logger.info(f"✅ HIGH confidence: {best_score:.3f}")
            return {
                "action": "direct_answer",
                "faq": best_faq,
                "score": best_score,
                "all_matches": faqs_with_scores
            }
        
        # 2. УТОЧНЕНИЕ (35-55%) - только если есть близкие варианты
        elif best_score >= self.medium_threshold:
            # Проверяем, есть ли ещё похожие с близким score
            close_matches = [
                (faq, score) for faq, score in faqs_with_scores[:5]
                if score >= self.medium_threshold * 0.85  # в пределах 85% от порога
            ]
            
            if len(close_matches) >= 2:
                logger.info(f"🤔 MEDIUM confidence with {len(close_matches)} close matches: {best_score:.3f}")
                return {
                    "action": "clarify",
                    "faq": best_faq,
                    "score": best_score,
                    "all_matches": close_matches[:3],  # макс 3 варианта
                    "message": "multiple_options"
                }
            else:
                # Только 1 хороший вариант - показываем его!
                logger.info(f"✅ MEDIUM confidence but single good match: {best_score:.3f}")
                return {
                    "action": "direct_answer",
                    "faq": best_faq,
                    "score": best_score,
                    "all_matches": faqs_with_scores,
                    "message": "single_medium_match"
                }
        
        # 3. ПОКАЗАТЬ ПОХОЖИЕ (20-35%) - без GPT-генерации!
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
        
        # 4. НЕТ ОТВЕТА (<20%)
        else:
            logger.info(f"❌ Very LOW confidence: {best_score:.3f}")
            return {
                "action": "no_match",
                "score": best_score,
                "all_matches": faqs_with_scores[:3],  # показываем топ-3 для дебага
                "message": "no_match_found"
            }