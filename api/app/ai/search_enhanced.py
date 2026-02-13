# api/app/ai/search_enhanced.py - SIMPLIFIED VERSION
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text, select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class EnhancedSearchService:
    
    @staticmethod
    def _build_video_url(video_file_id: Optional[str]) -> Optional[str]:
        """
        Build Directus video URL from file_id
        
        Args:
            video_file_id: Directus file UUID
            
        Returns:
            Full URL to video asset or None
        """
        if not video_file_id:
            return None
        
        # Strip whitespace and check again
        video_file_id = str(video_file_id).strip()
        if not video_file_id or video_file_id == 'None':
            return None
        
        base_url = settings.DIRECTUS_URL.rstrip('/')
        
        # If token is configured, append it
        if settings.DIRECTUS_TOKEN:
            return f"{base_url}/assets/{video_file_id}?access_token={settings.DIRECTUS_TOKEN}"
        
        return f"{base_url}/assets/{video_file_id}"
    
    @staticmethod
    async def find_similar_faqs(
        session: AsyncSession,
        query_embedding: List[float],
        language: str,
        limit: int = 10
    ):
        """
        Find similar FAQs using vector search
        SIMPLIFIED: Assumes faq_content.video already contains UUID
        """
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        
        # ✅ УПРОЩЕННАЯ ВЕРСИЯ: video уже содержит UUID
        sql = text("""
            SELECT 
                faq_v2.id,
                faq_content.question,
                faq_content.answer_text,
                faq_content.video as video_file_id,
                faq_v2.category,
                faq_content.language,
                faq_v2.created_at,
                1 - (faq_content.question_embedding <=> CAST(:embedding AS vector)) as similarity
            FROM faq_content
            INNER JOIN faq_v2 ON faq_content.faq_id = faq_v2.id
            WHERE faq_content.language = :language
              AND faq_v2.is_active = TRUE
              AND faq_content.question_embedding IS NOT NULL
            ORDER BY faq_content.question_embedding <=> CAST(:embedding AS vector)
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
    async def keyword_search(
        session: AsyncSession,
        query_text: str,
        language: str,
        limit: int = 10
    ) -> List[Tuple]:
        """
        Keyword-based fallback search
        SIMPLIFIED: Assumes faq_content.video already contains UUID
        """
        # ✅ УПРОЩЕННАЯ ВЕРСИЯ
        sql = text("""
            SELECT 
                faq_v2.id,
                faq_content.question,
                faq_content.answer_text,
                faq_content.video as video_file_id,
                faq_v2.category,
                faq_content.language,
                faq_v2.created_at,
                ts_rank(
                    to_tsvector('simple', faq_content.question || ' ' || faq_content.answer_text),
                    plainto_tsquery('simple', :query)
                ) as relevance
            FROM faq_content
            INNER JOIN faq_v2 ON faq_content.faq_id = faq_v2.id
            WHERE faq_content.language = :language
              AND faq_v2.is_active = TRUE
              AND (
                  faq_content.question ILIKE :pattern
                  OR faq_content.answer_text ILIKE :pattern
              )
            ORDER BY relevance DESC
            LIMIT :limit
        """)
        
        pattern = f"%{query_text}%"
        
        result = await session.execute(
            sql,
            {
                "query": query_text,
                "pattern": pattern,
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
        try:
            sql = text("""
                UPDATE search_cache 
                SET hit_count = hit_count + 1, last_used_at = NOW()
                WHERE query_hash = :hash
                RETURNING faq_results
            """)
            
            result = await session.execute(sql, {"hash": query_hash})
            row = result.fetchone()
            
            if row:
                return row[0]
            return None
        except Exception as e:
            logger.warning(f"Cache check failed: {e}")
            return None
    
    @staticmethod
    async def save_to_cache(
        session: AsyncSession,
        query_hash: str,
        query_normalized: str,
        language: str,
        results: List[Dict]
    ):
        """Save cache"""
        try:
            sql = text("""
                INSERT INTO search_cache (query_hash, query_normalized, language, faq_results)
                VALUES (:hash, :normalized, :language, :results::jsonb)
                ON CONFLICT (query_hash) 
                DO UPDATE SET 
                    hit_count = search_cache.hit_count + 1,
                    last_used_at = NOW()
            """)
            
            import json
            results_json = json.dumps(results)
            
            await session.execute(
                sql,
                {
                    "hash": query_hash,
                    "normalized": query_normalized,
                    "language": language,
                    "results": results_json
                }
            )
        except Exception as e:
            logger.warning(f"Cache save failed: {e}")
    
    @staticmethod
    async def hybrid_search(
        session: AsyncSession,
        query_embedding: List[float],
        query_text: str,
        language: str,
        limit: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Hybrid search: vector + keyword fallback
        """
        # Primary: Vector search
        rows = await EnhancedSearchService.find_similar_faqs(
            session, query_embedding, language, limit
        )
        
        candidates = []
        for row in rows:
            video_file_id = row[3]  # UUID from faq_content.video
            
            # ✅ ЛОГИРОВАНИЕ для отладки
            if video_file_id:
                logger.info(f"FAQ {row[0]}: Found video_file_id = {video_file_id}")
            else:
                logger.debug(f"FAQ {row[0]}: No video")
            
            video_url = EnhancedSearchService._build_video_url(video_file_id)
            
            faq = {
                'id': row[0],
                'question': row[1],
                'answer_text': row[2],
                'video_url': video_url,
                'category': row[4],
                'language': row[5],
                'created_at': row[6]
            }
            score = float(row[7])
            candidates.append((faq, score))
        
        # Fallback: Keyword search if vector results are poor
        if not candidates or (candidates and candidates[0][1] < 0.5):
            logger.info("Vector search weak, trying keyword fallback")
            keyword_rows = await EnhancedSearchService.keyword_search(
                session, query_text, language, limit
            )
            
            for row in keyword_rows:
                # Skip if already in vector results
                if any(c[0]['id'] == row[0] for c in candidates):
                    continue
                
                video_file_id = row[3]
                video_url = EnhancedSearchService._build_video_url(video_file_id)
                
                faq = {
                    'id': row[0],
                    'question': row[1],
                    'answer_text': row[2],
                    'video_url': video_url,
                    'category': row[4],
                    'language': row[5],
                    'created_at': row[6]
                }
                score = float(row[7]) * 0.8
                candidates.append((faq, score))
        
        # Sort by score and limit
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]
    
    @staticmethod
    async def rerank_with_gpt(
        user_question: str,
        candidates: List[Tuple[Dict, float]],
        top_k: int = 3
    ) -> List[Tuple[Dict, float]]:
        """GPT reranking - disabled for now"""
        return candidates[:top_k]