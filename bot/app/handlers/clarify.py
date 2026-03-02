# bot/app/handlers/clarify.py
"""
Обработчик clarify-диалога.

Отвечает за:
  - Inline-кнопки clarify:choose:N  и  clarify:other
  - Текстовый ввод "1"/"2"/"3"/"4" когда pending_clarify активен
"""
import logging

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from app.services.clarify_state import get_pending, clear, resolve_choice
from app.services.ai_client import AIClient
from app.handlers.message import send_faq_answer, log_user_action

router = Router()
logger = logging.getLogger(__name__)


# ─── Вспомогательная функция ──────────────────────────────────────────────────

async def _deliver_option(
    message_or_callback,
    option: dict,
    language: str,
    user_id: str,
) -> None:
    """
    Доставить ответ по выбранному option.

    option = {"index": N, "title": "...", "faq_id": 123}

    Запрашивает FAQ по faq_id через API и отдаёт direct_answer.
    """
    # Определяем куда отправлять сообщение
    if isinstance(message_or_callback, CallbackQuery):
        send_target = message_or_callback.message
    else:
        send_target = message_or_callback

    faq_id = option.get("faq_id")
    title = option.get("title", "")

    if faq_id:
        # Есть конкретный faq_id — запрашиваем напрямую
        ai_client = AIClient()
        response = await ai_client.ask_by_faq_id(faq_id=faq_id)

        if response:
            await send_faq_answer(send_target, response, language)
            await log_user_action(
                telegram_id=user_id,
                question=title,
                matched_faq_id=faq_id,
                confidence=1.0,
            )
            return

    # Fallback — запросить по заголовку как обычный вопрос
    ai_client = AIClient()
    response = await ai_client.ask_question(
        question=title,
        user_id=user_id,
        language=language,
    )

    if response and response.get("action") == "direct_answer":
        await send_faq_answer(send_target, response, language)
        await log_user_action(
            telegram_id=user_id,
            question=title,
            matched_faq_id=response.get("faq_id"),
            confidence=response.get("confidence", 0.8),
        )
    else:
        # Ответ не найден
        if language == "kk":
            await send_target.answer("💡 Бұл тақырып бойынша ақпарат табылмады. Басқаша қойып көріңіз.")
        else:
            await send_target.answer("💡 По этой теме информация не найдена. Попробуйте переформулировать.")


# ─── Обработчик inline-кнопок ─────────────────────────────────────────────────

@router.callback_query(F.data.startswith("clarify:"))
async def handle_clarify_callback(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    data = callback.data  # "clarify:choose:0" или "clarify:other"

    state = get_pending(user_id)
    if state is None:
        # State истёк или не был установлен
        await callback.answer("⏱ Сессия истекла. Задайте вопрос заново.", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        return

    language = state["language"]
    options = state["options"]

    # ── "Басқа / Другое" ──────────────────────────────────────────────────────
    if data == "clarify:other":
        clear(user_id)
        await callback.message.edit_reply_markup(reply_markup=None)

        if language == "kk":
            prompt = "💬 Нақты қандай сұрақ? Қайта жазыңыз:"
        else:
            prompt = "💬 Уточните, какой именно вопрос вас интересует:"

        await callback.message.answer(prompt)
        await callback.answer()
        logger.info(f"[Clarify] user={user_id} chose 'other'")
        return

    # ── clarify:choose:N ──────────────────────────────────────────────────────
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
        logger.info(f"[Clarify] user={user_id} chose option {idx+1}: '{chosen['title'][:40]}'")

        # Сбрасываем state ДО отправки ответа
        clear(user_id)

        # Убираем кнопки с сообщения
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

        await callback.answer()
        await _deliver_option(callback, chosen, language, user_id)


# ─── Обработчик текстового ввода "1"-"4" ──────────────────────────────────────

@router.message(F.text.regexp(r'^[1-4]$|^[1️⃣2️⃣3️⃣4️⃣]$'))
async def handle_digit_choice(message: Message):
    """
    Перехватывает "1", "2", "3", "4" если есть pending clarify.
    Если pending нет — пропускает дальше (не блокирует обычные сообщения).
    """
    user_id = str(message.from_user.id)
    state = get_pending(user_id)

    if state is None:
        # Нет pending — не обрабатываем, пусть идёт в message handler
        return

    option = resolve_choice(user_id, message.text)
    if option is None:
        return

    language = state["language"]
    logger.info(f"[Clarify] user={user_id} digit choice '{message.text}' → '{option['title'][:40]}'")

    clear(user_id)
    await _deliver_option(message, option, language, user_id)


# ─── Обработчик точного совпадения с вариантом ────────────────────────────────

@router.message(F.text)
async def handle_text_as_clarify_choice(message: Message):
    """
    Если pending_clarify активен и текст совпадает с одним из вариантов
    (пользователь скопировал) — обрабатываем как выбор.

    Если не совпадает — пропускаем (идёт в основной message handler).

    ВАЖНО: этот router должен быть зарегистрирован ПЕРЕД основным message handler.
    """
    user_id = str(message.from_user.id)
    state = get_pending(user_id)

    if state is None:
        return  # нет pending — пропускаем

    option = resolve_choice(user_id, message.text)
    if option is None:
        # Не распознан как выбор — сбрасываем pending и обрабатываем как новый вопрос
        # Не делаем return — даём пройти в основной handler
        # Но сначала сбрасываем чтобы не зациклиться
        clear(user_id)
        return

    language = state["language"]
    logger.info(f"[Clarify] user={user_id} text match → '{option['title'][:40]}'")

    clear(user_id)
    await _deliver_option(message, option, language, user_id)