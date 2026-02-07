# api/app/ai/search_enhanced.py
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class EnhancedSearchService:
    
    @staticmethod
    async def get_synonyms(session: AsyncSession, language: str, query: str) -> List[str]:
        """Получить синонимы для обогащения запроса"""
        sql = text("""
            SELECT DISTINCT UNNEST(synonyms) as synonym
            FROM synonyms
            WHERE language = :language
            AND (
                term ILIKE :query
                OR :query ILIKE '%' || term || '%'
                OR EXISTS (
                    SELECT 1 FROM UNNEST(synonyms) s
                    WHERE :query ILIKE '%' || s || '%'
                )
            )
        """)
        
        result = await session.execute(sql, {"language": language, "query": f"%{query}%"})
        return [row[0] for row in result.fetchall()]
    
    @staticmethod
    async def check_cache(
        session: AsyncSession, 
        query_hash: str
    ) -> Optional[List[Dict]]:
        """Проверить кеш поисковых запросов"""
        sql = text("""
            UPDATE search_cache
            SET hit_count = hit_count + 1,
                last_used_at = NOW()
            WHERE query_hash = :hash
            RETURNING faq_results
        """)
        
        result = await session.execute(sql, {"hash": query_hash})
        row = result.fetchone()
        
        if row:
            logger.info(f"Cache HIT for query_hash={query_hash}")
            return row[0]  # JSONB результаты
        
        return None
    
    @staticmethod
    async def save_to_cache(
        session: AsyncSession,
        query_hash: str,
        query_normalized: str,
        language: str,
        results: List[Dict]
    ):
        """Сохранить результаты в кеш"""
        sql = text("""
            INSERT INTO search_cache (query_hash, language, query_normalized, faq_results)
            VALUES (:hash, :language, :query, :results::jsonb)
            ON CONFLICT (query_hash) DO UPDATE
            SET hit_count = search_cache.hit_count + 1,
                last_used_at = NOW()
        """)
        
        await session.execute(sql, {
            "hash": query_hash,
            "language": language,
            "query": query_normalized,
            "results": results
        })
    
    @staticmethod
    async def hybrid_search(
        session: AsyncSession,
        query_embedding: List[float],
        query_text: str,
        language: str,
        limit: int = 10
    ) -> List[Tuple[Dict[str, Any], float]]:
        """
        Гибридный поиск: vector similarity + keyword matching
        """
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        keywords = query_text.lower().split()
        
        # Гибридный поиск: 70% vector, 30% keyword
        sql = text("""
            WITH vector_scores AS (
                SELECT 
                    fc.id,
                    fc.faq_id,
                    fc.question,
                    fc.answer_text,
                    fc.video_url,
                    fc.language,
                    faq.category,
                    faq.created_at,
                    (1 - (fc.question_embedding <=> CAST(:embedding AS vector))) as vector_score
                FROM faq_content fc
                JOIN faq_v2 faq ON faq.id = fc.faq_id
                WHERE fc.language = :language
                AND fc.question_embedding IS NOT NULL
                AND faq.is_active = TRUE
            ),
            keyword_scores AS (
                SELECT 
                    fc.id,
                    SUM(
                        CASE 
                            WHEN fc.question_normalized ILIKE '%' || kw || '%' THEN 1.0
                            WHEN kw = ANY(fc.question_keywords) THEN 0.5
                            ELSE 0
                        END
                    ) / NULLIF(CARDINALITY(:keywords::text[]), 0) as keyword_score
                FROM faq_content fc
                CROSS JOIN UNNEST(:keywords::text[]) as kw
                WHERE fc.language = :language
                GROUP BY fc.id
            )
            SELECT 
                vs.faq_id,
                vs.question,
                vs.answer_text,
                vs.video_url,
                vs.category,
                vs.language,
                vs.created_at,
                (0.7 * vs.vector_score + 0.3 * COALESCE(ks.keyword_score, 0)) as hybrid_score
            FROM vector_scores vs
            LEFT JOIN keyword_scores ks ON vs.id = ks.id
            ORDER BY hybrid_score DESC
            LIMIT :limit
        """)
        
        result = await session.execute(sql, {
            "embedding": embedding_str,
            "language": language,
            "keywords": keywords,
            "limit": limit
        })
        
        rows = result.fetchall()
        
        faqs_with_scores = []
        for row in rows:
            faq_data = {
                'id': row[0],
                'question': row[1],
                'answer_text': row[2],
                'video_url': row[3],
                'category': row[4],
                'language': row[5],
                'created_at': row[6]
            }
            score = row[7]
            faqs_with_scores.append((faq_data, score))
        
        logger.info(f"Hybrid search found {len(faqs_with_scores)} results")
        return faqs_with_scores
    
    @staticmethod
    async def rerank_with_gpt(
        user_question: str,
        candidates: List[Tuple[Dict, float]],
        top_k: int = 3
    ) -> List[Tuple[Dict, float]]:
        """
        GPT-based reranking для финальной точности
        """
        from openai import AsyncOpenAI
        
        if len(candidates) <= top_k:
            return candidates
        
        client = AsyncOpenAI()
        
        # Подготовка промпта
        faq_list = "\n".join([
            f"{i+1}. {faq['question']}"
            for i, (faq, _) in enumerate(candidates[:10])
        ])
        
        prompt = f"""Дан вопрос пользователя и список FAQ.
Оцени релевантность каждого FAQ вопросу по шкале 0-10.

Вопрос: {user_question}

FAQ:
{faq_list}

Верни JSON: {{"1": score, "2": score, ...}}"""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            scores = eval(response.choices[0].message.content)
            
            # Пересчитываем scores
            reranked = []
            for i, (faq, original_score) in enumerate(candidates):
                gpt_score = scores.get(str(i+1), 0) / 10.0
                # Комбинируем: 60% GPT + 40% vector
                final_score = 0.6 * gpt_score + 0.4 * original_score
                reranked.append((faq, final_score))
            
            reranked.sort(key=lambda x: x[1], reverse=True)
            return reranked[:top_k]
        
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return candidates[:top_k]