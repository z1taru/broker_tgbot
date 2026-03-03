# bot/app/keyboards/clarify.py
"""
Клавиатура для clarify-диалога.

Варианты выводятся В ТЕКСТЕ СООБЩЕНИЯ (не в кнопках),
кнопки — только цифры 1-4 и "Басқа / Другое".

Структура callback_data:
    clarify:choose:0   ← индекс в массиве options (0-based)
    clarify:other      ← кнопка "Басқа / Другое"
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


_DIGIT_EMOJI = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
_DIGIT_LABEL = ["1", "2", "3", "4"]


def build_clarify_keyboard(
    options: list[dict],
    language: str = "kk",
) -> InlineKeyboardMarkup:
    """
    Строит inline keyboard с ЦИФРОВЫМИ кнопками.
    Текст вариантов — в сообщении, не в кнопках.
    """
    buttons = []

    # Одна строка со всеми цифрами
    digit_row = []
    for i, opt in enumerate(options[:4]):
        digit_row.append(
            InlineKeyboardButton(
                text=_DIGIT_EMOJI[i],
                callback_data=f"clarify:choose:{i}",
            )
        )
    if digit_row:
        buttons.append(digit_row)

    # Кнопка "Другое" отдельной строкой
    other_text = "❓ Басқа сұрақ" if language == "kk" else "❓ Другое"
    buttons.append([
        InlineKeyboardButton(
            text=other_text,
            callback_data="clarify:other",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_clarify_message(
    language: str,
    original_query: str,
    options: list[dict],
) -> str:
    """
    Текст сообщения с вариантами — полный текст каждого варианта.
    Пользователь нажимает цифру 1/2/3/4 на кнопке.
    """
    if language == "kk":
        header = f"🔍 <b>«{original_query}»</b> — нақтылау қажет.\n\nСізге не керек?\n"
    else:
        header = f"🔍 <b>«{original_query}»</b> — нужно уточнить.\n\nЧто именно вас интересует?\n"

    lines = [header]
    for i, opt in enumerate(options[:4]):
        emoji = _DIGIT_EMOJI[i]
        lines.append(f"{emoji} {opt['title']}")

    return "\n".join(lines)


# Оставляем для обратной совместимости
def build_clarify_header(language: str, original_query: str) -> str:
    """Устаревший метод — используй build_clarify_message вместо него."""
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