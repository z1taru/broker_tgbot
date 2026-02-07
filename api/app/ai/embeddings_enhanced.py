# api/app/ai/embeddings_enhanced.py
from typing import List, Optional, Dict, Any
import re
import hashlib
from openai import AsyncOpenAI
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class EnhancedEmbeddingService:
    def __init__(self):
        self.client = AsyncOpenAI()
        self.model = "text-embedding-3-small"
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Нормализация текста для лучшего поиска"""
        # Lowercase
        text = text.lower()
        # Убрать лишние пробелы
        text = re.sub(r'\s+', ' ', text)
        # Убрать пунктуацию (кроме важной)
        text = re.sub(r'[^\w\s\-]', '', text)
        return text.strip()
    
    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Извлечение ключевых слов"""
        # Стоп-слова для казахского и русского
        stop_words = {
            'kk': {'не', 'қалай', 'бол', 'деген', 'керек', 'және', 'үшін'},
            'ru': {'как', 'что', 'если', 'это', 'для', 'или', 'и', 'в', 'на'}
        }
        
        normalized = EnhancedEmbeddingService.normalize_text(text)
        words = normalized.split()
        
        # Убрать стоп-слова (для обоих языков)
        all_stop_words = stop_words['kk'] | stop_words['ru']
        keywords = [w for w in words if w not in all_stop_words and len(w) > 2]
        
        return keywords
    
    async def create_embedding_with_enrichment(
        self, 
        text: str,
        synonyms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Создание embedding с enrichment
        
        Returns:
            {
                'embedding': List[float],
                'normalized': str,
                'keywords': List[str],
                'hash': str
            }
        """
        # Обогащение текста синонимами
        enriched_text = text
        if synonyms:
            enriched_text = f"{text}. {' '.join(synonyms)}"
        
        # Создание embedding
        response = await self.client.embeddings.create(
            model=self.model,
            input=enriched_text
        )
        
        # Нормализация и извлечение keywords
        normalized = self.normalize_text(text)
        keywords = self.extract_keywords(text)
        
        # Хеш для кеширования
        text_hash = hashlib.md5(normalized.encode()).hexdigest()
        
        return {
            'embedding': response.data[0].embedding,
            'normalized': normalized,
            'keywords': keywords,
            'hash': text_hash
        }
    
    async def batch_create_embeddings(
        self, 
        texts: List[str],
        synonyms_map: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """Batch обработка для efficiency"""
        results = []
        
        for i, text in enumerate(texts):
            syns = synonyms_map.get(str(i), []) if synonyms_map else None
            result = await self.create_embedding_with_enrichment(text, syns)
            results.append(result)
        
        return results