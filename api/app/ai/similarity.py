# api/app/ai/similarity.py
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class SimilarityService:

    @staticmethod
    async def find_similar_faqs(session, query_embedding, language: str, limit: int = 5):
        """
        Find similar FAQs using cosine similarity
        Falls back to searching all languages if no results found
        
        Args:
            session: AsyncSession
            query_embedding: List[float] - embedding vector (1536 dimensions)
            language: str - language code ('kk' or 'ru')
            limit: int - max number of results
            
        Returns:
            List of tuples (FAQ object, similarity_score)
        """
        try:
            # Преобразуем список в строку формата PostgreSQL array
            embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
            
            # Сначала ищем по указанному языку
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
                    "query_embedding": embedding_str,
                    "language": language,
                    "limit": limit
                }
            )

            rows = result.fetchall()
            
            # Если не нашли по указанному языку, ищем по всем языкам
            if not rows:
                logger.warning(f"No FAQs found for language '{language}', searching all languages")
                
                sql_all = text("""
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
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                """)
                
                result = await session.execute(
                    sql_all,
                    {
                        "query_embedding": embedding_str,
                        "limit": limit
                    }
                )
                
                rows = result.fetchall()
                logger.info(f"Found {len(rows)} similar FAQs across all languages")
            else:
                logger.info(f"Found {len(rows)} similar FAQs for language '{language}'")
            
            return rows

        except Exception as e:
            logger.error(f"Error finding similar FAQs: {e}")
            raise