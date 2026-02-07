# api/app/scripts/generate_embeddings_v2.py
import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session_maker
from app.models.database import FAQ
from app.ai.embeddings_enhanced import EnhancedEmbeddingService
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

async def generate_embeddings_v2():
    """Generate enriched embeddings for all FAQ"""
    
    embedding_service = EnhancedEmbeddingService()
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        # Получить все FAQ без embeddings
        result = await session.execute(
            select(FAQ).where(FAQ.embedding.is_(None))
        )
        faqs = result.scalars().all()
        
        if not faqs:
            logger.info("All FAQs already have embeddings")
            return
        
        logger.info(f"Processing {len(faqs)} FAQs")
        
        for i, faq in enumerate(faqs, start=1):
            try:
                logger.info(f"[{i}/{len(faqs)}] Processing FAQ ID={faq.id}")
                
                # Создание enriched embedding
                enriched = await embedding_service.create_embedding_with_enrichment(
                    text=f"{faq.question} {faq.answer_text}",
                    synonyms=[]  # TODO: добавить синонимы из БД
                )
                
                # Обновление FAQ
                await session.execute(
                    update(FAQ)
                    .where(FAQ.id == faq.id)
                    .values(embedding=enriched['embedding'])
                )
                
                await session.commit()
                logger.info(f"✅ FAQ ID={faq.id} updated")
                
            except Exception as e:
                logger.error(f"❌ FAQ ID={faq.id} failed: {e}")
                await session.rollback()
                continue
        
        logger.info("✅ All embeddings generated!")

if __name__ == "__main__":
    asyncio.run(generate_embeddings_v2())