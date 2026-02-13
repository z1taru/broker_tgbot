#!/usr/bin/env python3
"""
Настройка Directus для публичного доступа к видео (ИСПРАВЛЕННАЯ ВЕРСИЯ)
Запуск: python3 setup_directus_access_v2.py
"""

import asyncio
import aiohttp
import os
from getpass import getpass

DIRECTUS_URL = os.getenv("DIRECTUS_URL", "http://localhost:8054")
DIRECTUS_ADMIN_EMAIL = os.getenv("DIRECTUS_ADMIN_EMAIL", "admin@example.com")
DIRECTUS_ADMIN_PASSWORD = os.getenv("DIRECTUS_ADMIN_PASSWORD")


async def login_to_directus(email: str, password: str):
    """Получить токен доступа через логин"""
    
    login_url = f"{DIRECTUS_URL}/auth/login"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                login_url,
                json={
                    "email": email,
                    "password": password
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data["data"]["access_token"]
                    return token
                else:
                    error_data = await resp.json()
                    print(f"❌ Ошибка входа: {error_data}")
                    return None
    except Exception as e:
        print(f"❌ Ошибка подключения к Directus: {e}")
        return None


async def create_static_token(admin_token: str):
    """Создать статический токен для API"""
    
    # В новой версии Directus токены создаются через /access-tokens
    tokens_url = f"{DIRECTUS_URL}/access-tokens"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                tokens_url,
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "name": "FAQ Bot API Token",
                    "expires_at": None  # Бессрочный токен
                }
            ) as resp:
                if resp.status in [200, 201]:
                    data = await resp.json()
                    static_token = data["data"]["token"]
                    return static_token
                else:
                    error_data = await resp.json()
                    print(f"⚠️  Ошибка создания токена: {error_data}")
                    
                    # Попробуем старый endpoint
                    tokens_url_old = f"{DIRECTUS_URL}/users/me/tokens"
                    async with session.post(
                        tokens_url_old,
                        headers={"Authorization": f"Bearer {admin_token}"},
                        json={"name": "FAQ Bot API Token"}
                    ) as resp2:
                        if resp2.status in [200, 201]:
                            data = await resp2.json()
                            return data["data"]["token"]
                        else:
                            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None


async def set_public_permissions_v2(admin_token: str):
    """Настроить права для публичной роли (НОВАЯ ВЕРСИЯ с policy)"""
    
    permissions_url = f"{DIRECTUS_URL}/permissions"
    
    # ИСПРАВЛЕНО: Добавлено поле policy
    permission = {
        "collection": "directus_files",
        "action": "read",
        "permissions": {},  # Пустые permissions = доступ ко всем записям
        "validation": None,
        "presets": None,
        "fields": ["*"],
        "policy": None,  # ✅ НОВОЕ: policy для публичной роли
        "role": None  # None = Public role
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Сначала получим существующие разрешения
            async with session.get(
                permissions_url,
                headers={"Authorization": f"Bearer {admin_token}"},
                params={"filter[collection][_eq]": "directus_files", "filter[role][_null]": True}
            ) as resp:
                if resp.status == 200:
                    existing = await resp.json()
                    
                    if existing.get("data"):
                        print(f"ℹ️  Публичное разрешение уже существует, обновляем...")
                        # Обновить существующее
                        perm_id = existing["data"][0]["id"]
                        async with session.patch(
                            f"{permissions_url}/{perm_id}",
                            headers={"Authorization": f"Bearer {admin_token}"},
                            json=permission
                        ) as update_resp:
                            if update_resp.status == 200:
                                print(f"✅ Публичный доступ к файлам обновлён")
                                return True
            
            # Создать новое разрешение
            async with session.post(
                permissions_url,
                headers={"Authorization": f"Bearer {admin_token}"},
                json=permission
            ) as resp:
                if resp.status in [200, 201]:
                    print(f"✅ Публичный доступ к файлам разрешён")
                    return True
                elif resp.status == 409:
                    print(f"ℹ️  Разрешение уже существует")
                    return True
                else:
                    error_data = await resp.json()
                    print(f"❌ Ошибка создания разрешения: {error_data}")
                    return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


async def test_video_access(token: str = None):
    """Проверить доступ к видео"""
    
    video_uuid = "b0c1034b-5a88-4a32-81fe-4aad9b624042"
    
    if token:
        video_url = f"{DIRECTUS_URL}/assets/{video_uuid}?access_token={token}"
    else:
        video_url = f"{DIRECTUS_URL}/assets/{video_uuid}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(video_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                return resp.status == 200
    except:
        return False


async def main():
    print("="*80)
    print("🔧 НАСТРОЙКА DIRECTUS ДЛЯ FAQ BOT (V2)")
    print("="*80)
    
    # Шаг 1: Получить данные для входа
    print("\n1️⃣ Введите данные администратора Directus:")
    
    email = input(f"   Email [{DIRECTUS_ADMIN_EMAIL}]: ").strip() or DIRECTUS_ADMIN_EMAIL
    
    if DIRECTUS_ADMIN_PASSWORD:
        password = DIRECTUS_ADMIN_PASSWORD
        print(f"   Password: (из .env)")
    else:
        password = getpass("   Password: ")
    
    # Шаг 2: Войти и получить токен
    print("\n2️⃣ Получение токена доступа...")
    admin_token = await login_to_directus(email, password)
    
    if not admin_token:
        print("\n❌ ОШИБКА: Не удалось войти в Directus")
        return
    
    print(f"✅ Успешный вход!")
    
    # Шаг 3: Выбор способа доступа
    print("\n3️⃣ Выберите способ доступа к видео:")
    print("   A) Публичный доступ (без токена) - РЕКОМЕНДУЕТСЯ")
    print("   B) Приватный доступ (с токеном)")
    
    choice = input("\n   Ваш выбор [A/B]: ").strip().upper() or "A"
    
    if choice == "A":
        print("\n📂 Настройка публичного доступа (с policy)...")
        
        success = await set_public_permissions_v2(admin_token)
        
        if success:
            await asyncio.sleep(2)
            can_access = await test_video_access()
            
            if can_access:
                print("\n🎉 УСПЕХ! Видео доступны публично")
                print(f"\n✅ Ваш video URL:")
                print(f"   http://localhost:8054/assets/b0c1034b-5a88-4a32-81fe-4aad9b624042")
                print(f"\n💡 В .env используйте:")
                print(f"   DIRECTUS_URL=http://directus:8055")
                print(f"   DIRECTUS_TOKEN=  # Оставьте пустым")
            else:
                print("\n⚠️  Публичный доступ настроен, но видео недоступно")
                print("💡 Возможно нужно подождать или перезапустить Directus:")
                print("   docker-compose restart directus")
                print("\n   Или попробуйте вариант B (токен)")
        else:
            print("\n⚠️  Не удалось настроить публичный доступ")
            print("💡 Попробуйте вариант B (токен)")
    
    else:  # choice == "B"
        print("\n🔑 Создание статического токена...")
        
        static_token = await create_static_token(admin_token)
        
        if static_token:
            print(f"\n✅ Токен создан!")
            print(f"\n📋 Добавьте в .env:")
            print(f"   DIRECTUS_URL=http://directus:8055")
            print(f"   DIRECTUS_TOKEN={static_token}")
            
            can_access = await test_video_access(static_token)
            
            if can_access:
                print(f"\n🎉 УСПЕХ! Видео доступны с токеном")
            else:
                print(f"\n⚠️  Доступ с токеном не работает")
        else:
            print("\n❌ Не удалось создать токен")
            print("\n💡 АЛЬТЕРНАТИВНОЕ РЕШЕНИЕ:")
            print("1. Откройте http://localhost:8054/admin")
            print("2. Settings → Access Tokens")
            print("3. Создайте токен вручную")
            print("4. Добавьте в .env")
    
    print("\n" + "="*80)
    print("📝 СЛЕДУЮЩИЕ ШАГИ:")
    print("="*80)
    print("1. Обновите .env с новыми настройками")
    print("2. Перезапустите API:")
    print("   docker-compose restart api")
    print("3. Проверьте доступ:")
    print("   python3 test_video_url.py")
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())