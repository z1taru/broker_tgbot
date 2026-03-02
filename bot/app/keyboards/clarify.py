# bot/app/keyboards/clarify.py
"""
Клавиатура для clarify-диалога.

Структура callback_data:
    clarify:choose:0   ← индекс в массиве options (0-based)
    clarify:other      ← кнопка "Басқа / Другое"
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


_DIGIT_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]


def build_clarify_keyboard(
    options: list[dict],
    language: str = "kk",
) -> InlineKeyboardMarkup:
    """
    Строит inline keyboard из списка options.

    options: [{"index": 1, "title": "...", "faq_id": 123}, ...]
    Берём не больше 4.
    """
    buttons = []

    for i, opt in enumerate(options[:4]):
        emoji = _DIGIT_EMOJI[i]
        # Обрезаем длинные заголовки для кнопки (Telegram limit 64 chars)
        btn_text = f"{emoji} {opt['title']}"
        if len(btn_text) > 60:
            btn_text = btn_text[:57] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"clarify:choose:{i}",
            )
        ])

    # Кнопка "Другое"
    other_text = "❓ Басқа сұрақ" if language == "kk" else "❓ Другое"
    buttons.append([
        InlineKeyboardButton(
            text=other_text,
            callback_data="clarify:other",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_clarify_header(language: str, original_query: str) -> str:
    """Текст сообщения над клавиатурой."""
    if language == "kk":
        return (
            f"🔍 <b>«{original_query}»</b> — нақтылау қажет.\n\n"
            "Сізге не керек?"
        )
    else:
        return (
            f"🔍 <b>«{original_query}»</b> — нужно уточнить.\n\n"
            "Что именно вас интересует?"
        )