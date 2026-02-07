# api/app/services/rag_pipeline.py
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.embeddings_enhanced import EnhancedEmbeddingService
from app.ai.search_enhanced import EnhancedSearchService
from app.ai.language_detector import LanguageDetector
from app.core.logging_config import get_logger

logger = get_logger(__name__)

class RAGPipeline:
    def __init__(self):
        self.embedding_service = EnhancedEmbeddingService()
        self.search_service = EnhancedSearchService()
        self.lang_detector = LanguageDetector()
    
    async def process_query(
        self,
        session: AsyncSession,
        user_question: str,
        language: str = "auto",
        use_cache: bool = True,
        use_rerank: bool = True
    ) -> Dict[str, Any]:
        """
        Полный RAG pipeline:
        1. Language detection
        2. Query enrichment (synonyms)
        3. Embedding generation
        4. Cache check
        5. Hybrid search (vector + keyword)
        6. GPT reranking
        7. Cache save
        """
        
        # Шаг 1: Определение языка
        if language == "auto":
            language = self.lang_detector.detect(user_question)
        
        logger.info(f"Processing query in language: {language}")
        
        # Шаг 2: Query enrichment с синонимами
        synonyms = await self.search_service.get_synonyms(
            session, language, user_question
        )
        logger.info(f"Found {len(synonyms)} synonyms: {synonyms}")
        
        # Шаг 3: Создание embedding с enrichment
        enriched_data = await self.embedding_service.create_embedding_with_enrichment(
            user_question,
            synonyms=synonyms
        )
        
        query_embedding = enriched_data['embedding']
        query_hash = enriched_data['hash']
        query_normalized = enriched_data['normalized']
        
        # Шаг 4: Проверка кеша
        if use_cache:
            cached_results = await self.search_service.check_cache(
                session, query_hash
            )
            if cached_results:
                logger.info("Returning cached results")
                return {
                    'results': cached_results,
                    'from_cache': True,
                    'language': language
                }
        
        # Шаг 5: Hybrid search
        candidates = await self.search_service.hybrid_search(
            session=session,
            query_embedding=query_embedding,
            query_text=query_normalized,
            language=language,
            limit=10
        )
        
        if not candidates:
            logger.warning("No candidates found")
            return {
                'results': [],
                'from_cache': False,
                'language': language
            }
        
        # Шаг 6: GPT Reranking
        if use_rerank and len(candidates) > 3:
            logger.info("Applying GPT reranking")
            candidates = await self.search_service.rerank_with_gpt(
                user_question=user_question,
                candidates=candidates,
                top_k=5
            )
        
        # Шаг 7: Формирование результатов
        results = [
            {
                'faq_id': faq['id'],
                'question': faq['question'],
                'answer': faq['answer_text'],
                'video_url': faq.get('video_url'),
                'category': faq['category'],
                'score': float(score),
                'rank': i + 1
            }
            for i, (faq, score) in enumerate(candidates)
        ]
        
        # Шаг 8: Сохранение в кеш
        if use_cache:
            await self.search_service.save_to_cache(
                session=session,
                query_hash=query_hash,
                query_normalized=query_normalized,
                language=language,
                results=results
            )
        
        await session.commit()
        
        return {
            'results': results,
            'from_cache': False,
            'language': language,
            'synonyms_used': synonyms
        }