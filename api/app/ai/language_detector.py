from app.core.logging_config import get_logger

logger = get_logger(__name__)


class LanguageDetector:
    def detect(self, text: str) -> str:
        """
        Simple language detection for Kazakh and Russian
        Returns: 'kk' for Kazakh, 'ru' for Russian
        """
        kazakh_chars = set('әіңғүұқөһӘІҢҒҮҰҚӨҺ')
        
        text_chars = set(text.lower())
        kazakh_count = len(text_chars & kazakh_chars)
        
        if kazakh_count > 0:
            logger.info("Detected language: Kazakh")
            return "kk"
        else:
            logger.info("Detected language: Russian")
            return "ru"