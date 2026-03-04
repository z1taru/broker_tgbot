# bot/app/handlers/clarify.py
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from app.services.clarify_state import get_pending, clear, resolve_choice
from app.services.ai_client import AIClient
from app.handlers.message import send_faq_answer, log_user_action

router = Router()
logger = logging.getLogger(__name__)


async def _deliver_option(
    message_or_callback,
    option: dict,
    language: str,
    user_id: str,
) -> None:
    if isinstance(message_or_callback, CallbackQuery):
        send_target = message_or_callback.message
    else:
        send_target = message_or_callback

    faq_id = option.get("faq_id")
    title = option.get("title", "")

    logger.info(f"[Clarify._deliver_option] faq_id={faq_id} title='{title[:50]}' lang={language}")

    if not faq_id:
        logger.error(f"[Clarify._deliver_option] faq_id is None/empty — cannot fetch answer")
        if language == "kk":
            await send_target.answer("⚠️ Жауапты жүктеу кезінде қате орын алды. Қайталап көріңіз.")
        else:
            await send_target.answer("⚠️ Ошибка загрузки ответа. Попробуйте ещё раз.")
        return

    ai_client = AIClient()
    response = await ai_client.ask_by_faq_id(faq_id=faq_id)

    logger.info(f"[Clarify._deliver_option] ask_by_faq_id response={response}")

    if response and response.get("action") == "direct_answer":
        await send_faq_answer(send_target, response, language)
        await log_user_action(
            telegram_id=user_id,
            question=title,
            matched_faq_id=faq_id,
            confidence=1.0,
        )
        return

    logger.error(
        f"[Clarify._deliver_option] Bad response from ask_by_faq_id: "
        f"faq_id={faq_id} response={response}"
    )

    if language == "kk":
        await send_target.answer("⚠️ Жауапты жүктеу кезінде қате орын алды. Қайталап көріңіз.")
    else:
        await send_target.answer("⚠️ Ошибка загрузки ответа. Попробуйте ещё раз.")


@router.callback_query(F.data.startswith("clarify:"))
async def handle_clarify_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = callback.data

    state = get_pending(user_id)
    if state is None:
        await callback.answer("⏱ Сессия истекла. Задайте вопрос заново.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    language = state["language"]
    options = state["options"]

    if data == "clarify:other":
        clear(user_id)
        await callback.message.edit_reply_markup(reply_markup=None)
        if language == "kk":
            prompt = "💬 Нақты қандай сұрақ? Қайта жазыңыз:"
        else:
            prompt = "💬 Уточните, какой именно вопрос вас интересует:"
        await callback.message.answer(prompt)
        await callback.answer()
        return

    if data.startswith("clarify:choose:"):
        try:
            idx = int(data.split(":")[-1])
        except ValueError:
            await callback.answer("Ошибка", show_alert=True)
            return

        if idx >= len(options):
            await callback.answer("Ошибка выбора", show_alert=True)
            return

        chosen = options[idx]
        logger.info(
            f"[Clarify] user={user_id} chose idx={idx} "
            f"faq_id={chosen.get('faq_id')} title='{chosen['title'][:40]}'"
        )

        clear(user_id)

        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.answer()
        await _deliver_option(callback, chosen, language, user_id)


@router.message(F.text.regexp(r'^[1-4]$|^[1️⃣2️⃣3️⃣4️⃣]$'))
async def handle_digit_choice(message: Message):
    user_id = str(message.from_user.id)
    state = get_pending(user_id)

    if state is None:
        return

    option = resolve_choice(user_id, message.text)
    if option is None:
        return

    language = state["language"]
    clear(user_id)
    await _deliver_option(message, option, language, user_id)