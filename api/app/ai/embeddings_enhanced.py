# api/app/ai/embeddings_enhanced.py
from typing import List, Optional, Dict, Any
import re
import hashlib
from openai import AsyncOpenAI
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class EmbeddingService:
    """Production embedding service with OpenAI text-embedding-3-small"""
    
    def __init__(self):
        self.client = AsyncOpenAI()
        self.model = "text-embedding-3-small"
        self.dimension = 1536
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for better search quality"""
        text = text.lower()
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'[^\w\s\-]', '', text)
        return text.strip()
    
    @staticmethod
    def extract_keywords(text: str) -> List[str]:
        """Extract keywords (bilingual stopwords)"""
        stop_words = {
            'не', 'қалай', 'бол', 'деген', 'керек', 'және', 'үшін',
            'как', 'что', 'если', 'это', 'для', 'или', 'и', 'в', 'на'
        }
        
        normalized = EmbeddingService.normalize_text(text)
        words = normalized.split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        
        return keywords
    
    async def create_embedding(self, text: str) -> List[float]:
        """
        Create single embedding vector
        
        Args:
            text: Input text
            
        Returns:
            List of floats (1536 dimensions)
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        
        except Exception as e:
            logger.error(f"Embedding creation failed: {e}")
            raise
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Batch create embeddings (up to 2048 texts)
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [item.embedding for item in response.data]
        
        except Exception as e:
            logger.error(f"Batch embedding creation failed: {e}")
            raise
    
    async def create_embedding_with_enrichment(
        self, 
        text: str,
        synonyms: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Create embedding with metadata enrichment
        
        Returns:
            {
                'embedding': List[float],
                'normalized': str,
                'keywords': List[str],
                'hash': str
            }
        """
        # Enrich with synonyms
        enriched_text = text
        if synonyms:
            enriched_text = f"{text}. {' '.join(synonyms)}"
        
        # Create embedding
        embedding = await self.create_embedding(enriched_text)
        
        # Extract metadata
        normalized = self.normalize_text(text)
        keywords = self.extract_keywords(text)
        text_hash = hashlib.md5(normalized.encode()).hexdigest()
        
        return {
            'embedding': embedding,
            'normalized': normalized,
            'keywords': keywords,
            'hash': text_hash
        }
    
    async def batch_create_embeddings_with_enrichment(
        self, 
        texts: List[str],
        synonyms_map: Optional[Dict[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """Batch create with enrichment metadata"""
        results = []
        
        for i, text in enumerate(texts):
            syns = synonyms_map.get(str(i), []) if synonyms_map else None
            result = await self.create_embedding_with_enrichment(text, syns)
            results.append(result)
        
        return results


# Backward compatibility alias
EnhancedEmbeddingService = EmbeddingService