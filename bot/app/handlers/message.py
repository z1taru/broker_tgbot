# bot/app/handlers/message.py
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
import aiohttp
import logging

from app.config import settings
from app.services.ai_client import AIClient
from app.core.database import get_session_maker
from app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)


@router.message(F.text & ~F.text.startswith('/'))
async def handle_text_message(message: Message):
    """
    Handle user text messages with AI
    """
    user_id = str(message.from_user.id)
    question = message.text
    
    await message.answer("🔍 Іздеп жатырмын...")
    
    ai_client = AIClient()
    response = await ai_client.ask_question(
        question=question,
        user_id=user_id,
        language="auto"
    )
    
    if not response:
        await message.answer(
            "Кешіріңіз, қате орын алды. Қайталап көріңіз немесе қолдау қызметіне жазыңыз."
        )
        return
    
    action = response.get("action")
    
    if action == "direct_answer":
        await send_faq_answer(message, response)
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=response.get("faq_id"),
            confidence=response.get("confidence", 0.0)
        )
    
    elif action == "clarify":
        clarification_text = response.get("message", "Сұрағыңызды нақтылаңыз.")
        await message.answer(clarification_text)
    
    else:
        fallback_text = response.get("message", "Кешіріңіз, жауап таппадым.")
        await message.answer(fallback_text)
        
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=response.get("confidence", 0.0)
        )


async def send_faq_answer(message: Message, response: dict):
    """Send FAQ answer with optional video"""
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


async def log_user_action(
    telegram_id: str,
    question: str,
    matched_faq_id: int,
    confidence: float
):
    """Log user action to database"""
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