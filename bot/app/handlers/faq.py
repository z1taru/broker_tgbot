from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
import aiohttp
import logging

from bot.app.config import settings
from bot.app.keyboards.inline import get_questions_keyboard, get_back_keyboard
from bot.app.core.database import get_session_maker
from bot.app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("category:"))
async def show_category_questions(callback: CallbackQuery):
    """
    Показать вопросы из выбранной категории
    """
    category = callback.data.split(":", 1)[1]
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.API_BASE_URL}/faq/category/{category}"
            ) as resp:
                if resp.status == 200:
                    faqs = await resp.json()
                    
                    keyboard = get_questions_keyboard(faqs)
                    
                    await callback.message.edit_text(
                        f"Санаттағы сұрақтар:\n\nСұрақты таңда:",
                        reply_markup=keyboard
                    )
                    await callback.answer()
                elif resp.status == 404:
                    await callback.answer("Санат табылмады", show_alert=True)
                else:
                    await callback.answer("Сұрақтарды жүктеу қатесі", show_alert=True)
    except Exception as e:
        logger.error(f"Error fetching category questions: {e}")
        await callback.answer("Қате орын алды", show_alert=True)


@router.callback_query(F.data.startswith("faq:"))
async def show_faq_answer(callback: CallbackQuery):
    """
    Показать ответ на выбранный вопрос
    """
    faq_id = callback.data.split(":", 1)[1]
    telegram_id = str(callback.from_user.id)
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{settings.API_BASE_URL}/faq/{faq_id}"
            ) as resp:
                if resp.status != 200:
                    await callback.answer("Жауап табылмады", show_alert=True)
                    return
                
                faq = await resp.json()
        
        await log_user_action(
            telegram_id=telegram_id,
            question=faq["question"],
            matched_faq_id=int(faq_id),
            confidence=1.0
        )
        
        keyboard = get_back_keyboard()
        caption_text = (
            f"❓ <b>{faq['question']}</b>\n\n"
            f"💡 {faq['answer_text']}"
        )
        
        if faq.get("video_url"):
            video_url = faq["video_url"]
            video_full_url = f"{settings.API_BASE_URL}/videos/{video_url}"
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(video_full_url) as video_resp:
                        if video_resp.status == 200:
                            video_data = await video_resp.read()
                            
                            video_file = BufferedInputFile(
                                video_data, 
                                filename=video_url
                            )
                            
                            await callback.message.answer_video(
                                video=video_file,
                                caption=caption_text,
                                reply_markup=keyboard
                            )
                        else:
                            logger.error(f"Failed to download video: {video_resp.status}")
                            await callback.message.answer(
                                caption_text,
                                reply_markup=keyboard
                            )
                            await callback.message.answer(
                                f"⚠️ Видео уақытша қолжетімсіз"
                            )
            except Exception as e:
                logger.error(f"Error sending video: {e}")
                await callback.message.answer(
                    caption_text,
                    reply_markup=keyboard
                )
                await callback.message.answer(
                    f"⚠️ Видео жіберу кезінде қате орын алды"
                )
        else:
            await callback.message.answer(
                caption_text,
                reply_markup=keyboard
            )
        
        await callback.answer()
        
    except Exception as e:
        logger.error(f"Error showing FAQ answer: {e}")
        await callback.answer("Жауапты алу кезінде қате орын алды", show_alert=True)


async def log_user_action(
    telegram_id: str,
    question: str,
    matched_faq_id: int,
    confidence: float
):
    """
    Записать действие пользователя в БД
    """
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