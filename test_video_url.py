#!/usr/bin/env python3
"""
Быстрая диагностика video URL через Directus
Запуск: python3 test_video_url.py
"""

import asyncio
import aiohttp
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine



DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:aldik07bak@localhost:5432/faq_db")
DIRECTUS_URL = os.getenv("DIRECTUS_URL", "http://localhost:8054")
DIRECTUS_TOKEN = os.getenv("DIRECTUS_TOKEN", "")


async def test_video_access():
    """Проверка доступности видео через Directus"""
    
    print("="*80)
    print("🔍 ТЕСТ ДОСТУПНОСТИ ВИДЕО ЧЕРЕЗ DIRECTUS")
    print("="*80)
    
    # 1. Получить video UUID из БД
    engine = create_async_engine(DATABASE_URL, echo=False)
    
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT 
                fc.id,
                fc.question,
                fc.video,
                df.filename_download
            FROM faq_content fc
            JOIN directus_files df ON fc.video = df.id
            WHERE fc.video IS NOT NULL
            LIMIT 1
        """))
        
        row = result.fetchone()
        
        if not row:
            print("❌ Нет FAQ с видео в базе!")
            return
        
        faq_id, question, video_uuid, filename = row
        print(f"\n✅ Найден FAQ с видео:")
        print(f"   FAQ ID: {faq_id}")
        print(f"   Вопрос: {question[:50]}...")
        print(f"   Video UUID: {video_uuid}")
        print(f"   Filename: {filename}")
    
    await engine.dispose()
    
    # 2. Построить URL
    base_url = DIRECTUS_URL.rstrip('/')
    
    if DIRECTUS_TOKEN:
        video_url = f"{base_url}/assets/{video_uuid}?access_token={DIRECTUS_TOKEN}"
        print(f"\n🔑 URL с токеном: {video_url}")
    else:
        video_url = f"{base_url}/assets/{video_uuid}"
        print(f"\n🌐 URL без токена: {video_url}")
    
    # 3. Проверить доступность
    print(f"\n⏳ Проверяем доступность...")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(video_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                print(f"\n📊 Результат:")
                print(f"   Status: {resp.status}")
                print(f"   Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
                print(f"   Content-Length: {resp.headers.get('Content-Length', 'N/A')} bytes")
                
                if resp.status == 200:
                    print("\n✅ Видео ДОСТУПНО!")
                    
                    # Попробуем скачать первые 1MB
                    print("\n⏳ Скачиваем первые 1MB для проверки...")
                    async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=30)) as get_resp:
                        chunk_size = 0
                        async for chunk in get_resp.content.iter_chunked(1024 * 1024):  # 1MB
                            chunk_size += len(chunk)
                            break
                        
                        print(f"✅ Скачано {chunk_size} bytes")
                        print("\n🎉 ВСЁ РАБОТАЕТ! Видео можно скачать.")
                
                elif resp.status == 401:
                    print("\n❌ ОШИБКА 401: Требуется авторизация")
                    print("\n💡 РЕШЕНИЕ:")
                    print("   1. Откройте http://localhost:8054/admin")
                    print("   2. Settings → Access Tokens → Create Token")
                    print("   3. Добавьте в .env:")
                    print(f"      DIRECTUS_TOKEN=ваш_токен")
                
                elif resp.status == 404:
                    print("\n❌ ОШИБКА 404: Файл не найден")
                    print("\n💡 РЕШЕНИЕ:")
                    print("   Проверьте, что видео загружено в Directus:")
                    print(f"   http://localhost:8054/admin/content/directus_files")
                
                else:
                    print(f"\n❌ НЕОЖИДАННЫЙ СТАТУС: {resp.status}")
    
    except aiohttp.ClientError as e:
        print(f"\n❌ ОШИБКА ПОДКЛЮЧЕНИЯ: {e}")
        print("\n💡 РЕШЕНИЕ:")
        print("   Проверьте, что Directus запущен:")
        print("   docker ps | grep directus")
        print("   docker-compose up -d directus")
    
    except Exception as e:
        print(f"\n❌ НЕОЖИДАННАЯ ОШИБКА: {e}")
    
    print("\n" + "="*80)


async def test_api_response():
    """Проверка ответа API с video_url"""
    
    print("\n" + "="*80)
    print("🔍 ТЕСТ ОТВЕТА API")
    print("="*80)
    
    api_url = "http://localhost:8000/api/ask"
    
    payload = {
        "question": "второй счет Freedom",
        "user_id": "test",
        "language": "ru"
    }
    
    print(f"\n⏳ Отправляем запрос в API...")
    print(f"   URL: {api_url}")
    print(f"   Question: {payload['question']}")
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                api_url,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    print(f"\n✅ API вернул ответ:")
                    print(f"   Action: {data.get('action')}")
                    print(f"   Confidence: {data.get('confidence', 0):.3f}")
                    print(f"   FAQ ID: {data.get('faq_id')}")
                    
                    video_url = data.get('video_url')
                    if video_url:
                        print(f"   Video URL: {video_url}")
                        print("\n✅ API ВОЗВРАЩАЕТ video_url!")
                    else:
                        print(f"   Video URL: NULL")
                        print("\n❌ API НЕ ВОЗВРАЩАЕТ video_url")
                        print("\n💡 ПРИЧИНЫ:")
                        print("   1. Confidence слишком низкий")
                        print("   2. FAQ не найден")
                        print("   3. Ошибка в search_enhanced.py")
                else:
                    print(f"\n❌ API вернул ошибку: {resp.status}")
    
    except Exception as e:
        print(f"\n❌ ОШИБКА: {e}")
        print("\n💡 РЕШЕНИЕ:")
        print("   Проверьте, что API запущен:")
        print("   docker ps | grep api")
        print("   docker-compose up -d api")
    
    print("\n" + "="*80)


async def main():
    """Полная диагностика"""
    await test_video_access()
    await test_api_response()
    
    print("\n📝 ИТОГОВЫЕ РЕКОМЕНДАЦИИ:")
    print("="*80)
    print("1. Если видео доступно, но API не возвращает video_url:")
    print("   → Замените api/app/api/routes/ask.py")
    print("   → Перезапустите: docker-compose restart api")
    print()
    print("2. Если confidence слишком низкий (<40%):")
    print("   → Добавьте синонимы в БД")
    print("   → Пересоздайте embeddings")
    print()
    print("3. Если видео недоступно (401/404):")
    print("   → Проверьте DIRECTUS_TOKEN")
    print("   → Проверьте, что видео загружено в Directus")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())