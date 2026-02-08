# bot/app/handlers/message.py
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
import aiohttp
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.services.ai_client import AIClient
from app.core.database import get_session_maker
from app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)

# ID куратора для пересылки вопросов
CURATOR_CHAT_ID = os.getenv("CURATOR_TELEGRAM_ID", "YOUR_CURATOR_ID")


def detect_message_language(text: str) -> str:
    """
    Быстрое определение языка сообщения
    """
    kazakh_chars = set('әіңғүұқөһӘІҢҒҮҰҚӨҺ')
    
    if any(char in kazakh_chars for char in text.lower()):
        return "kk"
    return "ru"


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message, state: FSMContext):
    """
    Обработка текстовых сообщений с определением языка
    """
    user_id = str(message.from_user.id)
    question = message.text
    
    # Получаем сохранённый язык пользователя из FSM
    user_data = await state.get_data()
    saved_language = user_data.get("language")
    
    # Если язык не сохранён, определяем из сообщения
    if not saved_language:
        detected_language = detect_message_language(question)
    else:
        detected_language = saved_language
    
    # Показываем индикатор "печатает..." на правильном языке
    if detected_language == "kk":
        searching_msg = await message.answer("🔍 Іздеп жатырмын...")
    else:
        searching_msg = await message.answer("🔍 Ищу ответ...")
    
    logger.info(f"🌐 Detected language: {detected_language} | Question: {question[:50]}...")
    
    ai_client = AIClient()
    response = await ai_client.ask_question(
        question=question,
        user_id=user_id,
        language=detected_language
    )
    
    # Удаляем индикатор поиска
    try:
        await searching_msg.delete()
    except:
        pass
    
    if not response:
        error_text = "Кешіріңіз, қате орын алды. Қайталап көріңіз 🔄" if detected_language == "kk" else "Извините, произошла ошибка. Попробуйте ещё раз 🔄"
        await message.answer(error_text)
        return
    
    action = response.get("action")
    confidence = response.get("confidence", 0.0)
    
    logger.info(f"✨ Action: {action} | Confidence: {confidence:.3f} | User: {user_id}")
    
    # ============================================
    # ОБРАБОТКА ДЕЙСТВИЙ
    # ============================================
    
    # ✅ ПРЯМОЙ ОТВЕТ
    if action == "direct_answer":
        await send_faq_answer(message, response, detected_language)
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=response.get("faq_id"),
            confidence=confidence
        )
    
    # 🤔 УТОЧНЕНИЕ - показываем варианты БЕЗ кнопок с номерами
    elif action == "clarify":
        suggestions = response.get("suggestions", [])
        message_text = response.get("message", "")
        
        if suggestions:
            # Формируем текст с вариантами
            if detected_language == "kk":
                options_text = "\n\n📋 Мүмкін сіз мынаны білгіңіз келеді:\n\n"
            else:
                options_text = "\n\n📋 Возможно, вы хотели узнать:\n\n"
            
            for i, suggestion in enumerate(suggestions[:3], 1):
                options_text += f"{i}. {suggestion}\n"
            
            if detected_language == "kk":
                options_text += "\n💬 Сұрағыңызды нақтырақ қойыңыз"
            else:
                options_text += "\n💬 Уточните ваш вопрос"
            
            await message.answer(options_text)
        else:
            fallback = "Сұрақты нақтылаңыз" if detected_language == "kk" else "Уточните вопрос"
            await message.answer(message_text or fallback)
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence
        )
    
    # 📋 ПОКАЗАТЬ ПОХОЖИЕ
    elif action == "show_similar":
        suggestions = response.get("suggestions", [])
        
        if suggestions:
            if detected_language == "kk":
                similar_text = "📋 Ұқсас сұрақтар:\n\n"
            else:
                similar_text = "📋 Похожие вопросы:\n\n"
            
            for i, suggestion in enumerate(suggestions[:5], 1):
                similar_text += f"{i}. {suggestion}\n"
            
            if detected_language == "kk":
                similar_text += "\n💬 Қайталап сұраңыз немесе басқаша қойып көріңіз"
            else:
                similar_text += "\n💬 Переспросите или сформулируйте иначе"
            
            await message.answer(similar_text)
        else:
            fallback = "Басқаша қойып көріңіз" if detected_language == "kk" else "Попробуйте переформулировать"
            await message.answer(response.get("message", fallback))
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence
        )
    
    # ❌ НЕТ ОТВЕТА - отправляем куратору
    else:  # no_match
        no_answer = "Кешіріңіз, жауап таба алмадым" if detected_language == "kk" else "Извините, не нашёл ответа"
        await message.answer(response.get("message", no_answer))
        
        await send_to_curator(
            bot=message.bot,
            user=message.from_user,
            question=question
        )
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence
        )


async def send_faq_answer(message: Message, response: dict, language: str = "ru"):
    """
    Отправка ответа с видео (КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ)
    """
    answer_text = response.get("answer_text", "")
    video_url = response.get("video_url")
    
    logger.info(f"📤 Sending answer | video_url: {video_url} | language: {language}")
    
    if video_url:
        video_sent = False
        
        # СПОСОБ 1: Локальный файл (быстрее и надёжнее)
        local_video_path = Path(f"/app/videos/{video_url}")
        if local_video_path.exists():
            logger.info(f"📁 Found local video file: {local_video_path}")
            try:
                video_file = FSInputFile(local_video_path)
                await message.answer_video(
                    video=video_file,
                    caption=f"💡 {answer_text}",
                    supports_streaming=True
                )
                logger.info("✅ Video sent successfully from local file")
                video_sent = True
            except Exception as e:
                logger.error(f"❌ Error sending local video: {e}")
        else:
            logger.warning(f"⚠️ Local video not found: {local_video_path}")
        
        # СПОСОБ 2: HTTP скачивание (если локальный не сработал)
        if not video_sent:
            video_full_url = f"{settings.API_BASE_URL}/videos/{video_url}"
            logger.info(f"🎥 Attempting HTTP download from: {video_full_url}")
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_full_url, timeout=aiohttp.ClientTimeout(total=30)) as video_resp:
                        if video_resp.status == 200:
                            video_data = await video_resp.read()
                            logger.info(f"✅ Video downloaded via HTTP: {len(video_data)} bytes")
                            
                            video_file = BufferedInputFile(
                                video_data,
                                filename=video_url
                            )
                            
                            await message.answer_video(
                                video=video_file,
                                caption=f"💡 {answer_text}",
                                supports_streaming=True
                            )
                            logger.info("✅ Video sent successfully via HTTP")
                            video_sent = True
                        else:
                            logger.error(f"❌ HTTP download failed with status: {video_resp.status}")
            except asyncio.TimeoutError:
                logger.error("❌ Video download timeout (HTTP)")
            except Exception as e:
                logger.error(f"❌ Error downloading via HTTP: {e}")
        
        # СПОСОБ 3: Fallback - только текст
        if not video_sent:
            logger.error(f"❌ All video sending methods failed for: {video_url}")
            if language == "kk":
                await message.answer(f"💡 {answer_text}\n\n⚠️ Видео уақытша қолжетімсіз. Куратор қызметіне хабарласыңыз.")
            else:
                await message.answer(f"💡 {answer_text}\n\n⚠️ Видео временно недоступно. Обратитесь к куратору.")
    else:
        # Нет видео - отправляем только текст
        logger.info("📝 No video URL provided, sending text only")
        await message.answer(f"💡 {answer_text}")


async def send_to_curator(bot, user, question: str):
    """
    Отправка вопроса куратору (только в рабочее время 10:00-20:00)
    """
    try:
        current_hour = datetime.now().hour
        
        if 10 <= current_hour < 20:
            curator_message = (
                f"🆘 НОВЫЙ ВОПРОС ОТ СТУДЕНТА\n\n"
                f"👤 Студент: {user.full_name} (@{user.username or 'no_username'})\n"
                f"🆔 ID: {user.id}\n"
                f"📝 Вопрос: {question}\n"
                f"⏰ Время: {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"Ответьте студенту через /reply_{user.id}"
            )
            
            await bot.send_message(
                chat_id=CURATOR_CHAT_ID,
                text=curator_message
            )
            logger.info(f"✅ Sent to curator: User {user.id}")
        else:
            logger.info(f"⏰ Outside working hours ({current_hour}:00), not sending to curator")
            
    except Exception as e:
        logger.error(f"❌ Failed to send to curator: {e}")


async def log_user_action(
    telegram_id: str,
    question: str,
    matched_faq_id: int,
    confidence: float
):
    """Логирование действий пользователя"""
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            log_entry = Log(
                telegram_id=telegram_id,
                question=question,
                matched_faq_id=matched_faq_id,
                confidence=confidence
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        logger.error(f"Error logging user action: {e}")