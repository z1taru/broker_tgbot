# api/scripts/generate_embeddings.py
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from app.core.database import get_engine, get_session_maker
from app.models.database import FAQ
from app.ai.embeddings import EmbeddingService
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def generate_embeddings():
    """Generate embeddings for all FAQs without embeddings"""
    logger.info("Starting embedding generation...")
    
    engine = get_engine()
    session_maker = get_session_maker()
    
    async with session_maker() as session:
        result = await session.execute(
            select(FAQ).where(FAQ.embedding.is_(None))
        )
        faqs = result.scalars().all()
        
        if not faqs:
            logger.info("No FAQs without embeddings found")
            return
        
        logger.info(f"Found {len(faqs)} FAQs without embeddings")
        
        embedding_service = EmbeddingService()
        
        for i, faq in enumerate(faqs, 1):
            try:
                logger.info(f"Processing FAQ {i}/{len(faqs)}: ID={faq.id}")
                
                embedding = await embedding_service.create_embedding(faq.question)
                
                embedding_str = "[" + ",".join(map(str, embedding)) + "]"
                
                await session.execute(
                    update(FAQ)
                    .where(FAQ.id == faq.id)
                    .values(embedding=embedding_str)
                )
                
                await session.commit()
                logger.info(f"✅ Embedding created for FAQ {faq.id}")
                
            except Exception as e:
                logger.error(f"❌ Error processing FAQ {faq.id}: {e}")
                await session.rollback()
                continue
        
        logger.info("✅ Embedding generation complete")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(generate_embeddings())