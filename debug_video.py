#!/usr/bin/env python3
"""
Debug script для проверки отправки видео (Docker version)
"""
import asyncio
import aiohttp
import sys
import os
from pathlib import Path

# Настройки для Docker окружения
API_BASE_URL = os.getenv("API_BASE_URL", "http://api:8000")
VIDEO_FILENAME = "freedom_second_account.mp4"


async def check_video_availability():
    """Проверка доступности видео через API"""
    
    video_url = f"{API_BASE_URL}/videos/{VIDEO_FILENAME}"
    
    print(f"🔍 Checking video availability...")
    print(f"📍 URL: {video_url}")
    print("-" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                print(f"📡 HTTP Status: {resp.status}")
                print(f"📦 Content-Type: {resp.headers.get('Content-Type')}")
                print(f"📏 Content-Length: {resp.headers.get('Content-Length')} bytes")
                
                if resp.status == 200:
                    data = await resp.read()
                    size_mb = len(data) / 1024 / 1024
                    print(f"✅ Downloaded: {len(data)} bytes ({size_mb:.2f} MB)")
                    
                    # Проверяем, что это действительно видео
                    if b'ftyp' in data[:20] or b'moov' in data[:100]:
                        print("✅ Valid MP4 file signature detected")
                    else:
                        print(f"⚠️ Unexpected file signature: {data[:20]}")
                    
                    return True
                elif resp.status == 404:
                    print(f"❌ Video not found (404)")
                    print(f"💡 Make sure video files exist in ./videos/ directory")
                    return False
                else:
                    print(f"❌ Failed with status: {resp.status}")
                    text = await resp.text()
                    print(f"Response: {text[:200]}")
                    return False
                    
    except asyncio.TimeoutError:
        print("❌ Timeout error - API took too long to respond")
        return False
    except aiohttp.ClientConnectorError as e:
        print(f"❌ Connection error: {e}")
        print(f"💡 Make sure API container is running: docker-compose ps")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def test_api_ask():
    """Тест API /ask endpoint"""
    
    print(f"\n🔍 Testing /api/ask endpoint...")
    print(f"📍 API URL: {API_BASE_URL}")
    print("-" * 60)
    
    test_question = "как открыть второй счет"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE_URL}/api/ask",
                json={
                    "question": test_question,
                    "user_id": "debug_test",
                    "language": "ru"
                },
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                print(f"📡 HTTP Status: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ Response received")
                    print(f"📊 Action: {data.get('action')}")
                    print(f"📊 Confidence: {data.get('confidence'):.3f}")
                    print(f"📊 Video URL: {data.get('video_url')}")
                    print(f"📊 FAQ ID: {data.get('faq_id')}")
                    
                    if data.get('video_url'):
                        print(f"\n✅ Video URL is present: {data.get('video_url')}")
                        return data.get('video_url')
                    else:
                        print(f"\n⚠️ No video_url in response")
                        print(f"This might be OK if confidence is low or action is not 'direct_answer'")
                        return None
                else:
                    print(f"❌ Failed with status: {resp.status}")
                    text = await resp.text()
                    print(f"Response: {text[:200]}")
                    return None
                    
    except aiohttp.ClientConnectorError as e:
        print(f"❌ Cannot connect to API: {e}")
        print(f"💡 Check: docker-compose ps")
        print(f"💡 Check: docker-compose logs api")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def check_api_health():
    """Проверка здоровья API"""
    
    print(f"\n🔍 Checking API health...")
    print("-" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE_URL}/health",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✅ API is healthy")
                    print(f"📊 Status: {data.get('status')}")
                    print(f"📊 Database: {data.get('database')}")
                    print(f"📊 Version: {data.get('version')}")
                    return True
                else:
                    print(f"⚠️ API responded with status: {resp.status}")
                    return False
    except Exception as e:
        print(f"❌ API health check failed: {e}")
        return False


async def list_videos_in_api():
    """Попытка получить список видео из API"""
    
    print(f"\n🔍 Checking what videos are available in API...")
    print("-" * 60)
    
    # Пробуем несколько распространенных имён файлов
    test_videos = [
        "freedom_second_account.mp4",
        "currency_exchange.mp4",
        "tabys_pro_bonds.mp4",
        "freedom_support.mp4"
    ]
    
    found_videos = []
    
    async with aiohttp.ClientSession() as session:
        for video_name in test_videos:
            video_url = f"{API_BASE_URL}/videos/{video_name}"
            try:
                async with session.head(video_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        size = resp.headers.get('Content-Length', '?')
                        print(f"✅ {video_name} - {size} bytes")
                        found_videos.append(video_name)
                    else:
                        print(f"❌ {video_name} - not found (status {resp.status})")
            except Exception as e:
                print(f"❌ {video_name} - error: {e}")
    
    print(f"\n📊 Found {len(found_videos)} videos out of {len(test_videos)} tested")
    return found_videos


async def check_database():
    """Проверка данных в базе"""
    
    print(f"\n🔍 Checking FAQ database...")
    print("-" * 60)
    
    try:
        async with aiohttp.ClientSession() as session:
            # Получаем статистику FAQ
            async with session.get(
                f"{API_BASE_URL}/faq/stats/overview",
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    stats = data.get('data', {})
                    print(f"✅ Database accessible")
                    print(f"📊 Total FAQs: {stats.get('total', 0)}")
                    print(f"📊 With video: {stats.get('with_video', 0)}")
                    print(f"📊 Kazakh: {stats.get('kazakh', 0)}")
                    
                    if stats.get('with_video', 0) == 0:
                        print(f"\n⚠️ WARNING: No FAQs have video URLs in database!")
                        print(f"💡 Check your database initialization")
                    
                    return True
                else:
                    print(f"⚠️ Cannot get stats (status {resp.status})")
                    return False
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return False


async def main():
    """Запуск всех проверок"""
    
    print("=" * 60)
    print("🔧 VIDEO DEBUG TOOL (Docker Edition)")
    print("=" * 60)
    print(f"Environment: API_BASE_URL={API_BASE_URL}")
    print("=" * 60)
    
    # 1. Проверка здоровья API
    api_healthy = await check_api_health()
    
    if not api_healthy:
        print("\n❌ API is not healthy. Stopping checks.")
        print("\n💡 Try:")
        print("   docker-compose ps")
        print("   docker-compose logs api")
        return
    
    # 2. Проверка базы данных
    await check_database()
    
    # 3. Проверка API /ask
    video_url = await test_api_ask()
    
    # 4. Проверка доступности видео через HTTP
    if video_url:
        await check_video_availability()
    
    # 5. Список доступных видео
    found_videos = await list_videos_in_api()
    
    # Итоговые рекомендации
    print("\n" + "=" * 60)
    print("📋 RECOMMENDATIONS")
    print("=" * 60)
    
    if not found_videos:
        print("❌ No videos found in API!")
        print("\n💡 Solution:")
        print("   1. Check if videos exist: docker-compose exec api ls -la /app/videos/")
        print("   2. Add videos to ./videos/ folder on host")
        print("   3. Add volume in docker-compose.yml:")
        print("      bot:")
        print("        volumes:")
        print("          - ./videos:/app/videos:ro")
        print("   4. Restart: docker-compose restart bot")
    else:
        print(f"✅ Found {len(found_videos)} videos")
        print("💡 Bot should be able to send videos now")
    
    print("\n" + "=" * 60)
    print("✅ Debug complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())