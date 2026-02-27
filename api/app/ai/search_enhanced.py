# api/app/ai/search_enhanced.py
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging_config import get_logger
from app.config import settings

logger = get_logger(__name__)


class EnhancedSearchService:

    @staticmethod
    def _build_video_url(video_file_id: Optional[str]) -> Optional[str]:
        if not video_file_id:
            return None
        video_file_id = str(video_file_id).strip()
        if not video_file_id or video_file_id == 'None':
            return None
        base_url = settings.DIRECTUS_PUBLIC_URL.rstrip('/')
        return f"{base_url}/assets/{video_file_id}"

    @staticmethod
    def _deduplicate_by_faq_id(rows: list) -> list:
        """
        Дедупликация по faq_id — один faq_id = одна запись (первая по score).
        Решает проблему когда на одну тему несколько faq_content с разными видео.
        """
        seen = set()
        result = []
        for row in rows:
            faq_id = row[0]
            if faq_id not in seen:
                seen.add(faq_id)
                result.append(row)
            else:
                logger.debug(f"Dedup: skipping duplicate faq_id={faq_id}")
        return result

    @staticmethod
    async def find_similar_faqs(
        session: AsyncSession,
        query_embedding: List[float],
        language: str,
        limit: int = 10
    ):
        embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
        # Берём больше строк до дедупликации
        fetch_limit = limit * 3

        sql = text("""
            SELECT
                faq_v2.id,
                faq_content.question,
                faq_content.answer_text,
                faq_content.video as video_file_id,
                faq_v2.category,
                faq_content.language,
                faq_v2.created_at,
                faq_content.description_footer,
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
            {"embedding": embedding_str, "language": language, "limit": fetch_limit}
        )
        rows = result.fetchall()
        deduped = EnhancedSearchService._deduplicate_by_faq_id(rows)
        logger.info(f"Vector search: {len(rows)} rows → {len(deduped)} after dedup")
        return deduped[:limit]

    @staticmethod
    async def keyword_search(
        session: AsyncSession,
        query_text: str,
        language: str,
        limit: int = 10
    ) -> List[Tuple]:
        fetch_limit = limit * 3

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

        result = await session.execute(
            sql,
            {"query": query_text, "pattern": f"%{query_text}%",
             "language": language, "limit": fetch_limit}
        )
        rows = result.fetchall()
        deduped = EnhancedSearchService._deduplicate_by_faq_id(rows)
        logger.info(f"Keyword search: {len(rows)} rows → {len(deduped)} after dedup")
        return deduped[:limit]

    @staticmethod
    async def get_synonyms(session: AsyncSession, language: str, query: str) -> List[str]:
        try:
            sql = text("""
                SELECT DISTINCT UNNEST(synonyms) as synonym
                FROM synonyms
                WHERE language = :language
                AND (term ILIKE :query OR :query ILIKE '%' || term || '%')
            """)
            result = await session.execute(sql, {"language": language, "query": f"%{query}%"})
            return [row[0] for row in result.fetchall()]
        except Exception as e:
            logger.warning(f"Synonyms lookup failed: {e}")
            return []

    @staticmethod
    async def check_cache(session: AsyncSession, query_hash: str) -> Optional[List[Dict]]:
        try:
            sql = text("""
                UPDATE search_cache
                SET hit_count = hit_count + 1, last_used_at = NOW()
                WHERE query_hash = :hash
                RETURNING faq_results
            """)
            result = await session.execute(sql, {"hash": query_hash})
            row = result.fetchone()
            return row[0] if row else None
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
        try:
            import json
            sql = text("""
                INSERT INTO search_cache (query_hash, query_normalized, language, faq_results)
                VALUES (:hash, :normalized, :language, :results::jsonb)
                ON CONFLICT (query_hash)
                DO UPDATE SET hit_count = search_cache.hit_count + 1, last_used_at = NOW()
            """)
            await session.execute(sql, {
                "hash": query_hash, "normalized": query_normalized,
                "language": language, "results": json.dumps(results)
            })
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
        rows = await EnhancedSearchService.find_similar_faqs(
            session, query_embedding, language, limit
        )

        candidates = []
        seen_ids = set()

        for row in rows:
            faq_id = row[0]
            video_url = EnhancedSearchService._build_video_url(row[3])

            if row[3]:
                logger.info(f"FAQ {faq_id}: video_file_id={row[3]}")

            faq = {
                'id': faq_id,
                'question': row[1],
                'answer_text': row[2],
                'video_url': video_url,
                'category': row[4],
                'language': row[5],
                'created_at': row[6],
                'description_footer': row[7],
            }
            candidates.append((faq, float(row[8])))
            seen_ids.add(faq_id)

        # Keyword fallback если vector слабый
        if not candidates or candidates[0][1] < 0.5:
            logger.info("Vector weak, trying keyword fallback")
            kw_rows = await EnhancedSearchService.keyword_search(
                session, query_text, language, limit
            )
            for row in kw_rows:
                faq_id = row[0]
                if faq_id in seen_ids:
                    continue
                video_url = EnhancedSearchService._build_video_url(row[3])
                faq = {
                    'id': faq_id,
                    'question': row[1],
                    'answer_text': row[2],
                    'video_url': video_url,
                    'category': row[4],
                    'language': row[5],
                    'created_at': row[6],
                    'description_footer': None,
                }
                candidates.append((faq, float(row[7]) * 0.8))
                seen_ids.add(faq_id)

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]

    @staticmethod
    async def rerank_with_gpt(
        user_question: str,
        candidates: List[Tuple[Dict, float]],
        top_k: int = 3
    ) -> List[Tuple[Dict, float]]:
        return candidates[:top_k]