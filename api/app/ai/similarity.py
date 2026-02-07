from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class SimilarityService:

    @staticmethod
    async def find_similar_faqs(session, query_embedding, language: str, limit: int = 5):
        try:
            sql = text("""
                SELECT 
                    id,
                    question,
                    answer_text,
                    video_url,
                    category,
                    language,
                    created_at,
                    1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity
                FROM faq
                WHERE language = :language
                AND embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT :limit
            """)

            result = await session.execute(
                sql,
                {
                    "query_embedding": query_embedding,
                    "language": language,
                    "limit": limit
                }
            )

            rows = result.fetchall()
            return rows

        except Exception as e:
            logger.error(f"Error finding similar FAQs: {e}")
            raise
