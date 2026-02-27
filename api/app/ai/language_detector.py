from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LanguageDetector:
    def detect(self, text: str) -> str:
        """
        Тіл анықтау: қазақша немесе орысша.
        Әдепкі: 'kk' (Kazakh-first policy)
        """
        kazakh_chars = set('әіңғүұқөһӘІҢҒҮҰҚӨҺ')

        # Қазақ символдары бар ма?
        if any(c in kazakh_chars for c in text):
            logger.info("Detected language: Kazakh")
            return "kk"

        # Орыс тіліне тән маркерлер
        russian_markers = set('ёъ')
        russian_words = {
            'как', 'что', 'это', 'для', 'или', 'все', 'при', 'где',
            'когда', 'почему', 'зачем', 'нет', 'да', 'ещё', 'уже',
            'можно', 'нельзя', 'хочу', 'нужно', 'буду', 'есть'
        }

        has_russian_marker = any(c in russian_markers for c in text.lower())
        words = set(text.lower().split())
        has_russian_words = len(words & russian_words) >= 2

        if has_russian_marker or has_russian_words:
            logger.info("Detected language: Russian")
            return "ru"

        # Әдепкі — қазақша
        logger.info("Language unclear, defaulting to Kazakh (kk)")
        return "kk"