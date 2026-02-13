#!/usr/bin/env python3
"""
Диагностика и исправление проблемы с embeddings
Запуск: python3 fix_embeddings.py
"""

import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from openai import AsyncOpenAI

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:aldik07bak@localhost:5432/faq_db")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


async def check_embeddings():
    """Проверка состояния embeddings в БД"""
    
    print("="*80)
    print("🔍 ДИАГНОСТИКА EMBEDDINGS")
    print("="*80)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # 1. Проверка наличия embeddings
        print("\n1️⃣ Проверка наличия embeddings...")
        
        result = await conn.execute(text("""
            SELECT 
                COUNT(*) as total,
                COUNT(question_embedding) as with_embedding,
                COUNT(*) - COUNT(question_embedding) as without_embedding
            FROM faq_content
        """))
        
        row = result.fetchone()
        total = row[0]
        with_emb = row[1]
        without_emb = row[2]
        
        print(f"   Всего FAQ: {total}")
        print(f"   С embeddings: {with_emb}")
        print(f"   Без embeddings: {without_emb}")
        
        if without_emb > 0:
            print(f"\n❌ ПРОБЛЕМА: {without_emb} FAQ без embeddings!")
        else:
            print(f"\n✅ Все FAQ имеют embeddings")
        
        # 2. Проверка конкретного FAQ про "второй счет"
        print("\n2️⃣ Проверка FAQ про 'второй счет'...")
        
        result = await conn.execute(text("""
            SELECT 
                id,
                question,
                language,
                question_embedding IS NOT NULL as has_embedding
            FROM faq_content
            WHERE question ILIKE '%второй счет%' 
               OR question ILIKE '%екінші шот%'
               OR question ILIKE '%second account%'
            ORDER BY language
        """))
        
        rows = result.fetchall()
        
        if rows:
            for row in rows:
                status = "✅" if row[3] else "❌"
                print(f"   {status} FAQ #{row[0]}: {row[1][:50]}... ({row[2]})")
        else:
            print("   ❌ Не найдено FAQ про 'второй счет'!")
        
        # 3. Тестовый поиск с embeddings
        print("\n3️⃣ Тестовый поиск...")
        
        # Создаем тестовый embedding
        if OPENAI_API_KEY:
            client = AsyncOpenAI(api_key=OPENAI_API_KEY)
            
            try:
                response = await client.embeddings.create(
                    model="text-embedding-3-small",
                    input="второй счет Freedom"
                )
                
                test_embedding = response.data[0].embedding
                embedding_str = '[' + ','.join(map(str, test_embedding)) + ']'
                
                result = await conn.execute(text("""
                    SELECT 
                        fc.id,
                        fc.question,
                        fc.language,
                        1 - (fc.question_embedding <=> CAST(:embedding AS vector)) as similarity
                    FROM faq_content fc
                    WHERE fc.question_embedding IS NOT NULL
                    ORDER BY fc.question_embedding <=> CAST(:embedding AS vector)
                    LIMIT 5
                """), {"embedding": embedding_str})
                
                print("   Топ-5 похожих FAQ:")
                for row in result:
                    print(f"   {row[3]:.3f} - FAQ #{row[0]}: {row[1][:50]}... ({row[2]})")
                
            except Exception as e:
                print(f"   ❌ Ошибка создания embedding: {e}")
        else:
            print("   ⚠️  OPENAI_API_KEY не установлен, пропускаем тест")
    
    await engine.dispose()
    
    return without_emb > 0


async def regenerate_embeddings():
    """Пересоздать embeddings для всех FAQ"""
    
    print("\n" + "="*80)
    print("🔄 ПЕРЕСОЗДАНИЕ EMBEDDINGS")
    print("="*80)
    
    if not OPENAI_API_KEY:
        print("\n❌ ОШИБКА: OPENAI_API_KEY не установлен")
        print("💡 Добавьте в .env:")
        print("   OPENAI_API_KEY=sk-...")
        return False
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    async with engine.begin() as conn:
        # Получить все FAQ без embeddings
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
        
        print(f"\n📋 Найдено {len(faqs)} FAQ без embeddings")
        print("⏳ Создание embeddings...")
        
        for i, faq in enumerate(faqs, 1):
            faq_id, question, answer, language = faq
            
            try:
                # Создать embedding
                text_to_embed = f"{question} {answer}"
                
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
                
                print(f"   [{i}/{len(faqs)}] ✅ FAQ #{faq_id}: {question[:40]}...")
                
                # Rate limiting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                print(f"   [{i}/{len(faqs)}] ❌ FAQ #{faq_id}: {e}")
                continue
        
        print("\n✅ Embeddings созданы!")
    
    await engine.dispose()
    return True


async def add_synonyms():
    """Добавить синонимы для улучшения поиска"""
    
    print("\n" + "="*80)
    print("📚 ДОБАВЛЕНИЕ СИНОНИМОВ")
    print("="*80)
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        # Проверить, существует ли таблица
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'synonyms'
            )
        """))
        
        table_exists = result.scalar()
        
        if not table_exists:
            print("\n📋 Создание таблицы synonyms...")
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS synonyms (
                    id SERIAL PRIMARY KEY,
                    term VARCHAR(255) NOT NULL,
                    synonyms TEXT[] NOT NULL,
                    language VARCHAR(10) NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            print("   ✅ Таблица создана")
        
        # Добавить синонимы
        synonyms_data = [
            ("второй счет", ["екінші шот", "дополнительный счет", "новый счет", "second account"], "ru"),
            ("екінші шот", ["второй счет", "қосымша шот", "жаңа шот"], "kk"),
            ("Freedom", ["Фридом", "Freedom Broker", "Freedom брокер", "фридом брокер"], "ru"),
            ("облигация", ["облигации", "bonds", "мемлекеттік облигация", "корпоративная облигация"], "ru"),
            ("акция", ["акции", "stocks", "shares", "компания акциясы"], "ru"),
            ("валюта", ["валюта айырбасы", "обмен валюты", "currency exchange", "ақша айырбасы"], "ru"),
        ]
        
        print("\n⏳ Добавление синонимов...")
        
        for term, synonyms, language in synonyms_data:
            try:
                await conn.execute(text("""
                    INSERT INTO synonyms (term, synonyms, language)
                    VALUES (:term, :synonyms, :language)
                    ON CONFLICT DO NOTHING
                """), {
                    "term": term,
                    "synonyms": synonyms,
                    "language": language
                })
                
                print(f"   ✅ {term}: {len(synonyms)} синонимов")
                
            except Exception as e:
                print(f"   ⚠️  {term}: {e}")
        
        print("\n✅ Синонимы добавлены!")
    
    await engine.dispose()


async def main():
    print("="*80)
    print("🔧 FIX EMBEDDINGS & SEARCH")
    print("="*80)
    
    # Шаг 1: Диагностика
    needs_fix = await check_embeddings()
    
    # Шаг 2: Исправление если нужно
    if needs_fix:
        print("\n❓ Пересоздать embeddings? [Y/n]: ", end="")
        choice = input().strip().lower()
        
        if choice in ["y", "yes", ""]:
            success = await regenerate_embeddings()
            
            if success:
                # Повторная проверка
                print("\n🔍 Повторная проверка...")
                await check_embeddings()
    
    # Шаг 3: Добавление синонимов
    print("\n❓ Добавить синонимы для улучшения поиска? [Y/n]: ", end="")
    choice = input().strip().lower()
    
    if choice in ["y", "yes", ""]:
        await add_synonyms()
    
    # Финальные рекомендации
    print("\n" + "="*80)
    print("📝 СЛЕДУЮЩИЕ ШАГИ:")
    print("="*80)
    print("1. Перезапустите API:")
    print("   docker-compose restart api")
    print()
    print("2. Проверьте поиск:")
    print("   curl -X POST http://localhost:8000/api/ask \\")
    print('     -H "Content-Type: application/json" \\')
    print("     -d '{\"question\": \"второй счет\", \"user_id\": \"test\", \"language\": \"ru\"}'")
    print()
    print("3. Проверьте полный тест:")
    print("   python3 test_video_url.py")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())