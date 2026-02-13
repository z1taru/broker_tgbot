#!/usr/bin/env python3
"""
Автоматическая привязка видео к FAQ
Запуск: python3 attach_videos_auto.py
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:aldik07bak@localhost:5432/faq_db")


async def attach_videos():
    """Привязка видео к FAQ"""
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        
        print("\n" + "="*80)
        print("Шаг 1: Список FAQ")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                fc.id,
                fc.question,
                fc.language,
                fc.video
            FROM faq_content fc
            ORDER BY fc.id
        """))
        
        faqs = result.fetchall()
        for i, row in enumerate(faqs, 1):
            has_video = "✅" if row[3] else "❌"
            print(f"{i}. [{has_video}] {row[1][:60]}... ({row[2]})")
        
        print("\n" + "="*80)
        print("Шаг 2: Список видео")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                id,
                filename_download
            FROM directus_files
            WHERE type LIKE 'video%'
        """))
        
        videos = result.fetchall()
        for i, row in enumerate(videos, 1):
            print(f"{i}. {row[1]} (UUID: {row[0]})")
        
        print("\n" + "="*80)
        print("Шаг 3: Привязка видео")
        print("="*80)
        
        # Привязываем по ключевым словам
        mappings = [
            {
                "video_uuid": "b0c1034b-5a88-4a32-81fe-4aad9b624042",
                "keywords": ["second account", "второй счет", "екінші шот", "freedom"],
                "description": "freedom_second_account.mp4"
            },
            {
                "video_uuid": "42a0a218-0946-442b-96bf-06f346cfcbe6",
                "keywords": ["area", "площадь", "аумақ"],
                "description": "Area.mp4"
            }
        ]
        
        total_attached = 0
        
        for mapping in mappings:
            video_uuid = mapping["video_uuid"]
            keywords = mapping["keywords"]
            desc = mapping["description"]
            
            # Формируем WHERE условие
            conditions = " OR ".join([f"question ILIKE '%{kw}%'" for kw in keywords])
            
            sql = f"""
                UPDATE faq_content 
                SET video = :video_uuid
                WHERE ({conditions})
                  AND video IS NULL
                RETURNING id, question
            """
            
            result = await conn.execute(
                text(sql),
                {"video_uuid": video_uuid}
            )
            
            updated = result.fetchall()
            
            if updated:
                print(f"\n✅ Привязано {desc}:")
                for row in updated:
                    print(f"   - FAQ #{row[0]}: {row[1][:50]}...")
                total_attached += len(updated)
            else:
                print(f"\n⚠️  Не найдено FAQ для {desc}")
        
        print("\n" + "="*80)
        print("Шаг 4: Результат")
        print("="*80)
        
        result = await conn.execute(text("""
            SELECT 
                fc.id,
                fc.question,
                df.filename_download,
                fc.language
            FROM faq_content fc
            JOIN directus_files df ON fc.video = df.id
        """))
        
        attached = result.fetchall()
        
        print(f"\nВсего привязано видео: {len(attached)}")
        for row in attached:
            print(f"  - FAQ #{row[0]}: {row[1][:40]}... → {row[2]} ({row[3]})")
        
        if total_attached == 0:
            print("\n" + "="*80)
            print("⚠️  РУЧНАЯ ПРИВЯЗКА")
            print("="*80)
            print("\nАвтоматическая привязка не нашла подходящих FAQ.")
            print("Привяжите видео вручную:\n")
            print("1. Откройте: http://localhost:8055/admin")
            print("2. Перейдите в faq_content")
            print("3. Выберите FAQ")
            print("4. В поле 'video' выберите файл")
            print("5. Сохраните\n")
            print("Или используйте SQL:")
            print(f"""
UPDATE faq_content 
SET video = 'b0c1034b-5a88-4a32-81fe-4aad9b624042'::uuid
WHERE id = <номер_faq>;
            """)
    
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(attach_videos())