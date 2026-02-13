#!/usr/bin/env python3
"""
Генерация embeddings для FAQ (запуск внутри Docker API контейнера)
Использование:
  docker exec -it faq_api python3 /app/generate_embeddings_simple.py
"""

import asyncio
import sys
import os

# Добавить путь к модулям приложения
sys.path.insert(0, '/app')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from openai import AsyncOpenAI


async def generate_embeddings():
    """Генерация embeddings для всех FAQ"""
    
    # Получить настройки из переменных окружения
    DATABASE_URL = os.getenv("DATABASE_URL")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not DATABASE_URL:
        print("❌ ОШИБКА: DATABASE_URL не установлен")
        return False
    
    if not OPENAI_API_KEY:
        print("❌ ОШИБКА: OPENAI_API_KEY не установлен")
        print("💡 Добавьте в .env:")
        print("   OPENAI_API_KEY=sk-...")
        return False
    
    print("="*80)
    print("🔄 ГЕНЕРАЦИЯ EMBEDDINGS ДЛЯ FAQ")
    print("="*80)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async with engine.begin() as conn:
        # Получить FAQ без embeddings
        result = await conn.execute(text("""
            SELECT id, question, answer_text, language
            FROM faq_content
            WHERE question_embedding IS NULL
            ORDER BY id
        """))
        
        faqs = result.fetchall()
        
        if not faqs:
            print("\n✅ Все FAQ уже имеют embeddings")
            await engine.dispose()
            return True
        
        print(f"\n📋 Найдено {len(faqs)} FAQ без embeddings\n")
        
        for i, faq in enumerate(faqs, 1):
            faq_id, question, answer, language = faq
            
            try:
                # Создать embedding
                text_to_embed = f"{question} {answer}"
                
                print(f"[{i}/{len(faqs)}] FAQ #{faq_id} ({language}): {question[:50]}...")
                
                response = await client.embeddings.create(
                    model="text-embedding-3-small",
                    input=text_to_embed
                )
                
                embedding = response.data[0].embedding
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                # Сохранить в БД
                await conn.execute(text("""
                    UPDATE faq_content
                    SET question_embedding = CAST(:embedding AS vector)
                    WHERE id = :faq_id
                """), {
                    "embedding": embedding_str,
                    "faq_id": faq_id
                })
                
                print(f"          ✅ Embedding создан")
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"          ❌ ОШИБКА: {e}")
                continue
        
        print(f"\n✅ Embeddings созданы для {len(faqs)} FAQ!")
    
    await engine.dispose()
    return True


async def verify_embeddings():
    """Проверка созданных embeddings"""
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(question_embedding) as with_embedding
            FROM faq_content
        """))
        
        row = result.fetchone()
        total, with_emb = row[0], row[1]
        
        print(f"\n📊 Статистика:")
        print(f"   Всего FAQ: {total}")
        print(f"   С embeddings: {with_emb}")
        print(f"   Без embeddings: {total - with_emb}")
        
        if total == with_emb:
            print(f"\n🎉 Все FAQ имеют embeddings!")
        else:
            print(f"\n⚠️  Ещё {total - with_emb} FAQ без embeddings")
    
    await engine.dispose()


async def main():
    success = await generate_embeddings()
    
    if success:
        await verify_embeddings()
        
        print("\n" + "="*80)
        print("✅ ГОТОВО!")
        print("="*80)
        print("\nТеперь перезапустите API:")
        print("  docker-compose restart api")
        print("\nИ проверьте поиск:")
        print("  python3 test_video_url.py")
        print("="*80)


if __name__ == "__main__":
    asyncio.run(main())
    