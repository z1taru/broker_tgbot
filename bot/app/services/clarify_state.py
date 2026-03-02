# bot/app/services/clarify_state.py
"""
State-менеджер для clarify-диалога.

Хранит pending уточнение для каждого user_id.
TTL: 5 минут — после этого state сбрасывается автоматически.

Структура:
    _store[user_id] = {
        "options": [
            {"index": 1, "title": "...", "faq_id": 123},
            ...
        ],
        "language": "kk",
        "original_query": "фридом қалай",
        "created_at": float (timestamp)
    }
"""
from __future__ import annotations

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_TTL = 300  # 5 минут

# user_id (str) → state dict
_store: dict[str, dict] = {}


# ─── Public API ───────────────────────────────────────────────────────────────

def set_pending(
    user_id: str,
    options: list[dict],   # [{"index":1, "title":"...", "faq_id":123}, ...]
    language: str,
    original_query: str,
) -> None:
    """Сохранить pending clarify state."""
    _store[user_id] = {
        "options": options[:4],  # строго не больше 4
        "language": language,
        "original_query": original_query,
        "created_at": time.time(),
    }
    logger.info(
        f"[ClarifyState] SET user={user_id} lang={language} "
        f"options={len(options[:4])} query='{original_query[:40]}'"
    )


def get_pending(user_id: str) -> Optional[dict]:
    """Получить pending state если не истёк TTL."""
    state = _store.get(user_id)
    if state is None:
        return None
    if time.time() - state["created_at"] > _TTL:
        clear(user_id)
        logger.info(f"[ClarifyState] EXPIRED user={user_id}")
        return None
    return state


def clear(user_id: str) -> None:
    """Сбросить pending state."""
    if user_id in _store:
        del _store[user_id]
        logger.info(f"[ClarifyState] CLEAR user={user_id}")


def resolve_choice(user_id: str, text: str) -> Optional[dict]:
    """
    Попробовать распознать выбор пользователя из pending state.

    Варианты ввода:
      - "1", "2", "3", "4" (цифра)
      - "1️⃣", "2️⃣" и т.д. (эмодзи-цифра)
      - текст, совпадающий с одним из title (точно или нечётко)

    Возвращает выбранный option dict или None.
    """
    state = get_pending(user_id)
    if state is None:
        return None

    stripped = text.strip()
    options = state["options"]

    # 1. Цифра 1-4
    digit_map = {"1": 0, "2": 1, "3": 2, "4": 3,
                 "1️⃣": 0, "2️⃣": 1, "3️⃣": 2, "4️⃣": 3}
    if stripped in digit_map:
        idx = digit_map[stripped]
        if idx < len(options):
            logger.info(f"[ClarifyState] RESOLVED by digit '{stripped}' → option {idx+1}")
            return options[idx]

    # 2. Точное совпадение с title (пользователь скопировал)
    lower = stripped.lower()
    for opt in options:
        if opt["title"].lower() == lower:
            logger.info(f"[ClarifyState] RESOLVED by exact title match")
            return opt

    # 3. Частичное совпадение (пользователь написал похожее)
    for opt in options:
        opt_words = set(opt["title"].lower().split())
        user_words = set(lower.split())
        if len(opt_words) > 0:
            overlap = len(opt_words & user_words) / len(opt_words)
            if overlap >= 0.7:
                logger.info(f"[ClarifyState] RESOLVED by fuzzy match overlap={overlap:.2f}")
                return opt

    return None