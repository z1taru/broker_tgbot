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
from app.core.database import get_session_maker
from app.models.database import Log

router = Router()
logger = logging.getLogger(__name__)

CURATOR_CHAT_ID = os.getenv("CURATOR_TELEGRAM_ID", "YOUR_CURATOR_ID")


def _ui_language(text: str) -> str:
    """
    Язык ТОЛЬКО для UI-сообщений (индикатор "Ищу...").
    Настоящий язык ответа берётся из API response.

    Логика: казахский если есть спецсимволы ИЛИ казахские контекстные слова.
    Default: kk.
    """
    kazakh_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
    if any(c in kazakh_chars for c in text):
        return "kk"

    # Казахские слова без спецсимволов
    kk_context = {
        "деген", "туралы", "керек", "болады", "айтшы",
        "алу", "беру", "ашу", "сату", "және", "немесе",
        "аламын", "беремін",
    }
    lower_words = set(text.lower().split())
    if lower_words & kk_context:
        return "kk"

    # Казахские падежные окончания (-да, -нан, -ға и т.д.)
    kk_suffixes = ("да", "де", "та", "те", "дан", "ден", "тан", "тен",
                   "нан", "нен", "ға", "ге", "қа", "ке", "лар", "лер",
                   "дар", "дер", "тар", "тер")
    for word in text.lower().split():
        for suffix in kk_suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return "kk"

    # Явно русский
    ru_markers = set("ёъ")
    ru_words = {"как", "что", "это", "для", "или", "где", "нет", "да", "можно", "хочу"}
    if any(c in ru_markers for c in text.lower()):
        return "ru"
    if len(set(text.lower().split()) & ru_words) >= 2:
        return "ru"

    return "kk"  # default — казахский


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text_message(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    question = message.text

    # Язык только для индикатора загрузки
    ui_lang = _ui_language(question)

    if ui_lang == "kk":
        searching_msg = await message.answer("🔍 Іздеп жатырмын...")
    else:
        searching_msg = await message.answer("🔍 Ищу ответ...")

    logger.info(f"[MSG] ui_lang={ui_lang} | '{question[:60]}'")

    ai_client = AIClient()
    # Всегда отправляем language="auto" — LLM classifier в API определит язык по контексту
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
        err = "Кешіріңіз, қате орын алды 🔄" if ui_lang == "kk" else "Извините, ошибка. Попробуйте ещё раз 🔄"
        await message.answer(err)
        return

    action = response.get("action")
    confidence = response.get("confidence", 0.0)

    # Язык ответа берём из API (он определён LLM classifier-ом)
    # Если API не вернул — fallback на ui_lang
    response_language = response.get("detected_language", ui_lang)

    logger.info(f"[MSG] action={action} conf={confidence:.3f} lang={response_language}")

    # ── ПРЯМОЙ ОТВЕТ ──────────────────────────────────────────────────────────
    if action == "direct_answer":
        await send_faq_answer(message, response, response_language)
        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=response.get("faq_id"),
            confidence=confidence,
        )

    # ── УТОЧНЕНИЕ ─────────────────────────────────────────────────────────────
    elif action == "clarify":
        suggestions = response.get("suggestions", [])
        message_text = response.get("message", "")

        if suggestions:
            if response_language == "kk":
                header = "📋 Мүмкін сіз мынаны білгіңіз келеді:\n\n"
                footer = "\n💬 Сұрағыңызды нақтырақ қойыңыз"
            else:
                header = "📋 Возможно, вы хотели узнать:\n\n"
                footer = "\n💬 Уточните ваш вопрос"

            opts = "".join(f"{i}. {s}\n" for i, s in enumerate(suggestions[:4], 1))
            await message.answer(header + opts + footer)
        else:
            fallback = "Сұрақты нақтылаңыз" if response_language == "kk" else "Уточните вопрос"
            await message.answer(message_text or fallback)

        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence,
        )

    # ── ПОХОЖИЕ ───────────────────────────────────────────────────────────────
    elif action == "show_similar":
        suggestions = response.get("suggestions", [])
        if suggestions:
            if response_language == "kk":
                header = "📋 Ұқсас сұрақтар:\n\n"
                footer = "\n💬 Қайталап сұраңыз немесе басқаша қойып көріңіз"
            else:
                header = "📋 Похожие вопросы:\n\n"
                footer = "\n💬 Переспросите или сформулируйте иначе"

            opts = "".join(f"{i}. {s}\n" for i, s in enumerate(suggestions[:4], 1))
            await message.answer(header + opts + footer)
        else:
            fallback = "Басқаша қойып көріңіз" if response_language == "kk" else "Попробуйте переформулировать"
            await message.answer(response.get("message", fallback))

        await log_user_action(
            telegram_id=user_id,
            question=question,
            matched_faq_id=None,
            confidence=confidence,
        )

    # ── НЕТ ОТВЕТА ────────────────────────────────────────────────────────────
    else:
        no_ans = "Кешіріңіз, жауап таба алмадым" if response_language == "kk" else "Извините, не нашёл ответа"
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

    logger.info(f"[SEND] video_url={video_url} lang={language}")

    if video_url:
        video_sent = False
        try:
            timeout = aiohttp.ClientTimeout(total=settings.VIDEO_DOWNLOAD_TIMEOUT, connect=30)
            headers = {"User-Agent": "TelegramBot/1.0", "Accept": "*/*"}

            async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
                async with session.get(video_url) as resp:
                    logger.info(f"[VIDEO] status={resp.status}")
                    if resp.status == 200:
                        video_data = await resp.read()
                        size_mb = len(video_data) / (1024 * 1024)
                        logger.info(f"[VIDEO] size={size_mb:.2f}MB")

                        if size_mb > settings.MAX_VIDEO_SIZE_MB:
                            raise ValueError(f"Video {size_mb:.2f}MB exceeds limit")

                        filename = video_url.split("/")[-1].split("?")[0]
                        if not filename.endswith((".mp4", ".mov", ".avi", ".webm")):
                            filename = f"{filename}.mp4"

                        await message.answer_video(
                            video=BufferedInputFile(video_data, filename=filename),
                            caption=f"💡 {answer_text}"[:1024],
                            supports_streaming=True,
                        )
                        video_sent = True
                    elif resp.status == 403:
                        logger.error("[VIDEO] 403 — check Directus public role permissions")
                    elif resp.status == 404:
                        logger.error(f"[VIDEO] 404 — not found: {video_url}")
                    else:
                        logger.error(f"[VIDEO] failed status={resp.status}")

        except asyncio.TimeoutError:
            logger.error(f"[VIDEO] timeout after {settings.VIDEO_DOWNLOAD_TIMEOUT}s")
        except Exception as e:
            logger.error(f"[VIDEO] error: {type(e).__name__}: {e}", exc_info=True)

        if not video_sent:
            if language == "kk":
                await message.answer(f"💡 {answer_text}\n\n⚠️ Видео уақытша қолжетімсіз.")
            else:
                await message.answer(f"💡 {answer_text}\n\n⚠️ Видео временно недоступно.")
    else:
        await message.answer(f"💡 {answer_text}")


async def send_to_curator(bot, user, question: str):
    try:
        current_hour = datetime.now().hour
        if 10 <= current_hour < 20:
            text = (
                f"🆘 НОВЫЙ ВОПРОС\n\n"
                f"👤 {user.full_name} (@{user.username or 'no_username'})\n"
                f"🆔 {user.id}\n"
                f"📝 {question}\n"
                f"⏰ {datetime.now().strftime('%H:%M:%S')}"
            )
            await bot.send_message(chat_id=CURATOR_CHAT_ID, text=text)
    except Exception as e:
        logger.error(f"[CURATOR] failed: {e}")


async def log_user_action(
    telegram_id: str,
    question: str,
    matched_faq_id,
    confidence: float,
):
    try:
        session_maker = get_session_maker()
        async with session_maker() as session:
            log_entry = Log(
                telegram_id=telegram_id,
                question=question,
                matched_faq_id=matched_faq_id,
                confidence=confidence,
            )
            session.add(log_entry)
            await session.commit()
    except Exception as e:
        logger.error(f"[LOG] error: {e}")