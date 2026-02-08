# api/app/ai/search_enhanced.py
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging_config import get_logger
import json

logger = get_logger(__name__)


class EnhancedSearchService:
    
    @staticmethod
    async def find_similar_faqs(
        session: AsyncSession,
        query_embedding: List[float],
        language: str,
        limit: int = 10
    ):
        """
        Find similar FAQs using vector search
        """
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        sql = text("""
            SELECT 
                id,
                question,
                answer_text,
                video_url,
                category,
                language,
                created_at,
                1 - (embedding <=> CAST(:embedding AS vector)) as similarity
            FROM faq
            WHERE language = :language
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
        """)
        
        result = await session.execute(
            sql,
            {
                "embedding": embedding_str,
                "language": language,
                "limit": limit
            }
        )
        
        return result.fetchall()
    
    @staticmethod
    async def get_synonyms(session: AsyncSession, language: str, query: str) -> List[str]:
        """Get synonyms"""
        try:
            sql = text("""
                SELECT DISTINCT UNNEST(synonyms) as synonym
                FROM synonyms
                WHERE language = :language
                AND (
                    term ILIKE :query
                    OR :query ILIKE '%' || term || '%'
                )
            """)
            
            result = await session.execute(sql, {"language": language, "query": f"%{query}%"})
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"Synonyms lookup failed: {e}")
            return []
    
    @staticmethod
    async def check_cache(session: AsyncSession, query_hash: str) -> Optional[List[Dict]]:
        """Check cache"""
        return None  # Disabled for now
    
    @staticmethod
    async def save_to_cache(session: AsyncSession, query_hash: str, query_normalized: str, language: str, results: List[Dict]):
        """Save cache"""
        pass  # Disabled for now
    
    @staticmethod
    async def hybrid_search(
        session: AsyncSession,
        query_embedding: List[float],
        query_text: str,
        language: str,
        limit: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Hybrid search - fallback to simple vector search"""
        # For now, just use vector search
        rows = await EnhancedSearchService.find_similar_faqs(
            session, query_embedding, language, limit
        )
        
        candidates = []
        for row in rows:
            faq = {
                'id': row[0],
                'question': row[1],
                'answer_text': row[2],
                'video_url': row[3],
                'category': row[4],
                'language': row[5],
                'created_at': row[6]
            }
            score = float(row[7])
            candidates.append((faq, score))
        
        return candidates
    
    @staticmethod
    async def rerank_with_gpt(
        user_question: str,
        candidates: List[Tuple[Dict, float]],
        top_k: int = 3
    ) -> List[Tuple[Dict, float]]:
        """GPT reranking - disabled for now"""
        return candidates[:top_k]