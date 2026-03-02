# bot/app/handlers/message.py
from aiogram import Router, F
from aiogram.types import Message, BufferedInputFile
from aiogram.fsm.context import FSMContext
import aiohttp
import asyncio
import logging
import os
from datetime import datetime

from app.config import settings
from app.services.ai_client import AIClient
from app.services.clarify_state import set_pending, get_pending
from app.keyboards.clarify import build_clarify_keyboard, build_clarify_header
from app.core.database import get_session_maker
from app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)

CURATOR_CHAT_ID = os.getenv("CURATOR_TELEGRAM_ID", "YOUR_CURATOR_ID")


def _ui_language(text: str) -> str:
    kk_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
    if any(c in kk_chars for c in text):
        return "kk"
    kk_words = {"деген", "туралы", "керек", "болады", "айтшы",
                 "алу", "беру", "ашу", "сату", "және", "немесе"}
    if set(text.lower().split()) & kk_words:
        return "kk"
    kk_suffixes = ("да", "де", "та", "те", "дан", "ден", "тан", "тен",
                   "нан", "нен", "ға", "ге", "қа", "ке",
                   "лар", "лер", "дар", "дер", "тар", "тер")
    for word in text.lower().split():
        for s in kk_suffixes:
            if word.endswith(s) and len(word) > len(s) + 2:
                return "kk"
    ru_words = {"как", "что", "это", "для", "или", "где", "нет", "да", "можно", "хочу"}
    if len(set(text.lower().split()) & ru_words) >= 2:
        return "ru"
    return "kk"


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    question = message.text
    ui_lang = _ui_language(question)

    if ui_lang == "kk":
        searching_msg = await message.answer("🔍 Іздеп жатырмын...")
    else:
        searching_msg = await message.answer("🔍 Ищу ответ...")

    ai_client = AIClient()
    response = await ai_client.ask_question(
        question=question,
        user_id=user_id,
        language="auto",
    )

    try:
        await searching_msg.delete()
    except Exception:
        pass

    if not response:
        err = "Кешіріңіз, қате орын алды 🔄" if ui_lang == "kk" else "Извините, ошибка 🔄"
        await message.answer(err)
        return

    action = response.get("action")
    confidence = response.get("confidence", 0.0)
    language = response.get("detected_language", ui_lang)

    logger.info(f"[MSG] action={action} conf={confidence:.3f} lang={language} user={user_id}")

    if action == "direct_answer":
        await send_faq_answer(message, response, language)
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=response.get("faq_id"),
            confidence=confidence,
        )

    elif action in ("clarify", "show_similar"):
        suggestions = response.get("suggestions", [])
        faq_ids = response.get("suggestion_ids", [])

        options = []
        for i, title in enumerate(suggestions[:4]):
            options.append({
                "index": i,
                "title": title,
                "faq_id": faq_ids[i] if i < len(faq_ids) else None,
            })

        if not options:
            fallback = "Сұрақты нақтылаңыз" if language == "kk" else "Уточните вопрос"
            await message.answer(response.get("message", fallback))
            return

        set_pending(
            user_id=user_id,
            options=options,
            language=language,
            original_query=question,
        )

        header = build_clarify_header(language, question)
        keyboard = build_clarify_keyboard(options, language)
        await message.answer(header, reply_markup=keyboard)

        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence,
        )

    else:
        no_ans = "Кешіріңіз, жауап таба алмадым" if language == "kk" else "Извините, не нашёл ответа"
        await message.answer(response.get("message", no_ans))
        await send_to_curator(bot=message.bot, user=message.from_user, question=question)
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence,
        )


async def send_faq_answer(message: Message, response: dict, language: str = "kk"):
    answer_text = response.get("answer_text", "")
    video_url = response.get("video_url")

    if video_url:
        video_sent = False
        try:
            timeout = aiohttp.ClientTimeout(total=settings.VIDEO_DOWNLOAD_TIMEOUT, connect=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(video_url) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        size_mb = len(data) / (1024 * 1024)
                        if size_mb > settings.MAX_VIDEO_SIZE_MB:
                            raise ValueError(f"Video {size_mb:.1f}MB > limit")
                        filename = video_url.split("/")[-1].split("?")[0]
                        if not filename.endswith((".mp4", ".mov", ".avi", ".webm")):
                            filename += ".mp4"
                        await message.answer_video(
                            video=BufferedInputFile(data, filename=filename),
                            caption=f"💡 {answer_text}"[:1024],
                            supports_streaming=True,
                        )
                        video_sent = True
                    else:
                        logger.error(f"[VIDEO] status={resp.status}")
        except Exception as e:
            logger.error(f"[VIDEO] error: {e}", exc_info=True)

        if not video_sent:
            suffix = "\n\n⚠️ Видео уақытша қолжетімсіз." if language == "kk" else "\n\n⚠️ Видео временно недоступно."
            await message.answer(f"💡 {answer_text}{suffix}")
    else:
        await message.answer(f"💡 {answer_text}")


async def send_to_curator(bot, user, question: str):
    try:
        if 10 <= datetime.now().hour < 20:
            await bot.send_message(
                chat_id=CURATOR_CHAT_ID,
                text=(
                    f"🆘 НОВЫЙ ВОПРОС\n\n"
                    f"👤 {user.full_name} (@{user.username or '-'})\n"
                    f"🆔 {user.id}\n"
                    f"📝 {question}\n"
                    f"⏰ {datetime.now().strftime('%H:%M')}"
                ),
            )
    except Exception as e:
        logger.error(f"[CURATOR] {e}")


async def log_user_action(telegram_id, question, matched_faq_id, confidence):
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            session.add(Log(
                telegram_id=telegram_id,
                question=question,
                matched_faq_id=matched_faq_id,
                confidence=confidence,
            ))
            await session.commit()
    except Exception as e:
        logger.error(f"[LOG] {e}")