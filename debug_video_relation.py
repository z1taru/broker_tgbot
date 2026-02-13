#!/usr/bin/env python3
"""
Диагностика Directus video relation для FAQ
Запуск: python debug_video_relation.py
"""

import asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:aldik07bak@localhost:5432/faq_db")


async def diagnose_video_relation():
    """Проверка структуры Directus video relation"""
    
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    async with engine.begin() as conn:
        
        print("\n" + "="*80)
        print("1. Проверка колонки faq_content.video")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                column_name,
                data_type,
                udt_name,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'faq_content' 
              AND column_name = 'video'
        """))
        
        for row in result:
            print(f"Column: {row[0]}")
            print(f"Type: {row[1]} ({row[2]})")
            print(f"Nullable: {row[3]}")
        
        print("\n" + "="*80)
        print("2. Примеры данных из faq_content.video")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                id,
                question,
                video,
                pg_typeof(video) as video_type
            FROM faq_content
            WHERE video IS NOT NULL
            LIMIT 5
        """))
        
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"\nID: {row[0]}")
                print(f"Question: {row[1][:50]}...")
                print(f"Video: {row[2]}")
                print(f"Type: {row[3]}")
        else:
            print("❌ Нет данных с video!")
        
        print("\n" + "="*80)
        print("3. Проверка directus_files")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                id,
                filename_download,
                type,
                filesize
            FROM directus_files
            LIMIT 5
        """))
        
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"\nFile ID: {row[0]}")
                print(f"Filename: {row[1]}")
                print(f"Type: {row[2]}")
                print(f"Size: {row[3]} bytes")
        else:
            print("❌ Нет файлов в directus_files!")
        
        print("\n" + "="*80)
        print("4. Попытка JOIN faq_content + directus_files")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                fc.id as faq_id,
                fc.question,
                fc.video as video_field,
                df.id as file_id,
                df.filename_download
            FROM faq_content fc
            LEFT JOIN directus_files df ON fc.video::text = df.id::text
            WHERE fc.video IS NOT NULL
            LIMIT 5
        """))
        
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"\nFAQ ID: {row[0]}")
                print(f"Question: {row[1][:50]}...")
                print(f"Video field: {row[2]}")
                print(f"File ID (joined): {row[3]}")
                print(f"Filename: {row[4]}")
                
                if row[2] and not row[3]:
                    print("⚠️  WARNING: video field not empty but JOIN failed!")
        else:
            print("❌ JOIN не дал результатов!")
        
        print("\n" + "="*80)
        print("5. Проверка Directus relations metadata")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                many_collection,
                many_field,
                one_collection
            FROM directus_relations
            WHERE many_collection = 'faq_content'
               OR one_collection = 'faq_content'
            LIMIT 10
        """))
        
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"\n{row[0]}.{row[1]} → {row[2]}")
        else:
            print("ℹ️  Нет записей в directus_relations для faq_content")
        
        print("\n" + "="*80)
        print("6. РЕКОМЕНДАЦИИ")
        print("="*80)
        
        # Финальная проверка
        result = await conn.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(video) as with_video
            FROM faq_content
        """))
        
        row = result.fetchone()
        total = row[0]
        with_video = row[1]
        
        print(f"\nВсего FAQ: {total}")
        print(f"С video: {with_video}")
        print(f"Без video: {total - with_video}")
        
        if with_video == 0:
            print("\n❌ ПРОБЛЕМА: faq_content.video везде NULL!")
            print("Решение: Загрузить видео через Directus и связать с FAQ")
        else:
            print(f"\n✅ Есть {with_video} FAQ с video")
            print("Используйте SIMPLIFIED версию search_enhanced.py")
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(diagnose_video_relation())




