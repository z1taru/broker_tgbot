# api/app/scripts/generate_embeddings.py
import asyncio
import sys
from pathlib import Path

# Добавляем путь к приложению
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_maker, get_engine
from app.models.database import FAQ  # Правильный путь!
from app.core.logging_config import setup_logging, get_logger
from openai import AsyncOpenAI

# Настройка логирования
setup_logging()
logger = get_logger(__name__)

# Инициализация OpenAI клиента
openai_client = AsyncOpenAI()


async def generate_embeddings():
    """Generate embeddings for all FAQs without embeddings"""
    logger.info("Starting embedding generation...")

    engine = get_engine()
    session_maker = get_session_maker()

    async with session_maker() as session:  # type: AsyncSession
        # Получаем все FAQ без embedding
        result = await session.execute(
            select(FAQ).where(FAQ.embedding.is_(None))
        )
        faqs = result.scalars().all()

        if not faqs:
            logger.info("No FAQs without embeddings found")
            return

        logger.info(f"Found {len(faqs)} FAQs without embeddings")

        for i, faq in enumerate(faqs, start=1):
            # Сохраняем данные до try-блока
            faq_id = faq.id
            faq_question = faq.question
            faq_answer = faq.answer_text
            
            try:
                logger.info(f"Processing FAQ {i}/{len(faqs)}: ID={faq_id}")

                # Комбинируем вопрос и ответ для лучшего поиска
                text_for_embedding = f"{faq_question} {faq_answer}"

                # Создаём embedding через OpenAI API
                response = await openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text_for_embedding
                )

                # Получаем vector (это уже список из 1536 чисел)
                embedding = response.data[0].embedding

                # Обновляем запись в БД
                # pgvector автоматически преобразует Python list в PostgreSQL vector
                await session.execute(
                    update(FAQ)
                    .where(FAQ.id == faq_id)
                    .values(embedding=embedding)
                )

                await session.commit()

                logger.info(f"✅ Embedding saved for FAQ ID={faq_id}")

            except Exception as e:
                logger.error(f"❌ Error processing FAQ ID={faq_id}: {e}")
                await session.rollback()
                continue

        logger.info("✅ Embedding generation completed!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(generate_embeddings())