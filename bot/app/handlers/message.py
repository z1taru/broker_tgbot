# bot/app/handlers/message.py
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
import logging
import os
from datetime import datetime

from app.config import settings
from app.services.ai_client import AIClient
from app.core.database import get_session_maker
from app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)

# ID куратора для пересылки вопросов
CURATOR_CHAT_ID = os.getenv("CURATOR_TELEGRAM_ID", "YOUR_CURATOR_ID")


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """
    Обработка текстовых сообщений с улучшенной логикой
    """
    user_id = str(message.from_user.id)
    question = message.text
    
    # Показываем индикатор "печатает..."
    await message.answer("🔍 Іздеп жатырмын...")
    
    ai_client = AIClient()
    response = await ai_client.ask_question(
        question=question,
        user_id=user_id,
        language="auto"
    )
    
    if not response:
        await message.answer(
            "Кешіріңіз, қате орын алды. Қайталап көріңіз 🔄"
        )
        return
    
    action = response.get("action")
    confidence = response.get("confidence", 0.0)
    
    logger.info(f"Action: {action} | Confidence: {confidence:.3f} | User: {user_id}")
    
    # ============================================
    # ОБРАБОТКА ДЕЙСТВИЙ
    # ============================================
    
    # ✅ ПРЯМОЙ ОТВЕТ
    if action == "direct_answer":
        await send_faq_answer(message, response)
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=response.get("faq_id"),
            confidence=confidence
        )
    
    # 🤔 УТОЧНЕНИЕ - показываем кнопки
    elif action == "clarify":
        suggestions = response.get("suggestions", [])
        
        if suggestions:
            # Создаём inline кнопки для каждого варианта
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{i+1}️⃣ {q[:60]}..." if len(q) > 60 else f"{i+1}️⃣ {q}",
                    callback_data=f"select_q:{i}"
                )]
                for i, q in enumerate(suggestions[:3])
            ])
            
            await message.answer(
                response.get("message", "Выберите вариант:"),
                reply_markup=keyboard
            )
            
            # Сохраняем варианты в кеш для callback
            # TODO: использовать Redis или FSM для хранения состояния
            
        else:
            # Fallback - просто текст
            await message.answer(response.get("message", "Уточните вопрос"))
        
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
            # Создаём кнопки для похожих вопросов
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"• {q[:55]}..." if len(q) > 55 else f"• {q}",
                    callback_data=f"similar_q:{i}"
                )]
                for i, q in enumerate(suggestions[:5])
            ])
            
            await message.answer(
                response.get("message", "Похожие вопросы:"),
                reply_markup=keyboard
            )
        else:
            await message.answer(response.get("message", "Попробуйте переформулировать"))
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence
        )
    
    # ❌ НЕТ ОТВЕТА - отправляем куратору
    else:  # no_match
        await message.answer(response.get("message", "Извините, не нашёл ответа"))
        
        # Отправляем куратору (если в рабочее время)
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


async def send_faq_answer(message: Message, response: dict):
    """Отправка ответа с видео (если есть)"""
    answer_text = response.get("answer_text", "")
    video_url = response.get("video_url")
    
    if video_url:
        video_full_url = f"{settings.VIDEO_BASE_URL}/{video_url}"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video_full_url) as video_resp:
                    if video_resp.status == 200:
                        video_data = await video_resp.read()
                        
                        video_file = BufferedInputFile(
                            video_data,
                            filename=video_url
                        )
                        
                        await message.answer_video(
                            video=video_file,
                            caption=f"💡 {answer_text}"
                        )
                    else:
                        logger.error(f"Failed to download video: {video_resp.status}")
                        await message.answer(f"💡 {answer_text}")
        except Exception as e:
            logger.error(f"Error sending video: {e}")
            await message.answer(f"💡 {answer_text}")
    else:
        await message.answer(f"💡 {answer_text}")


async def send_to_curator(bot, user, question: str):
    """
    Отправка вопроса куратору (только в рабочее время 10:00-20:00)
    """
    try:
        current_hour = datetime.now().hour
        
        # Проверяем рабочее время
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


# ============================================
# CALLBACK HANDLERS для кнопок
# ============================================

@router.callback_query(F.data.startswith("select_q:"))
async def handle_question_selection(callback):
    """
    Обработка выбора вопроса из списка уточнений
    """
    # TODO: Получить сохранённые варианты из кеша/FSM
    # Пока заглушка
    await callback.answer("Функция в разработке")
    await callback.message.answer("Повторите вопрос, пожалуйста")


@router.callback_query(F.data.startswith("similar_q:"))
async def handle_similar_selection(callback):
    """
    Обработка выбора похожего вопроса
    """
    # TODO: аналогично
    await callback.answer("Функция в разработке")
    await callback.message.answer("Напишите номер вопроса")