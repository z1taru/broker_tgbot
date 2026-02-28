# api/app/ai/llm_classifier.py
from __future__ import annotations

import json
import hashlib
import time
from typing import Literal, Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, field_validator

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ─── Types ────────────────────────────────────────────────────────────────────

IntentType = Literal[
    "open_account",       # шот ашу / открытие счёта
    "deposit_withdraw",   # толтыру/шығару / пополнение/вывод
    "stocks_bonds",       # акциялар, облигациялар, ETF
    "dividends",          # дивиденд
    "currency",           # валюта айырбасы
    "commission_tariff",  # тариф, комиссия
    "tax",                # салық / налог ИИС
    "portfolio",          # портфель, стратегия
    "greeting",           # сәлем / привет
    "off_topic",          # вне тематики
    "general",            # общий брокерский вопрос
]


class ClassificationResult(BaseModel):
    language: Literal["ru", "kk"]
    vague: bool
    intent: IntentType
    slots: dict        # {"broker": "freedom", "account_type": "second", ...}
    confidence: float  # 0.0–1.0

    @field_validator("confidence")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# ─── In-memory cache ─────────────────────────────────────────────────────────

_intent_cache: dict[str, tuple[ClassificationResult, float]] = {}
_CACHE_TTL = 3600   # 1 час
_CACHE_MAX = 512


def _cache_key(text: str) -> str:
    return hashlib.md5(text.lower().strip().encode()).hexdigest()


def _cache_get(key: str) -> Optional[ClassificationResult]:
    entry = _intent_cache.get(key)
    if entry is None:
        return None
    result, ts = entry
    if time.time() - ts > _CACHE_TTL:
        _intent_cache.pop(key, None)
        return None
    return result


def _cache_set(key: str, result: ClassificationResult) -> None:
    if len(_intent_cache) >= _CACHE_MAX:
        oldest_key = min(_intent_cache, key=lambda k: _intent_cache[k][1])
        _intent_cache.pop(oldest_key, None)
    _intent_cache[key] = (result, time.time())


# ─── System Prompt ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
Сен — инвестициялық брокерлік боттың routing engine-і.
Сенің ЖАЛҒЫЗ міндетің — мәтінді классификациялау.
Пайдаланушыға ЕШҚАНДАЙ жауап берме. Тек JSON қайтар.

## JSON схемасы (markdown жоқ, тырнақша жоқ, тек таза JSON):
{
  "language": "ru" | "kk",
  "vague": true | false,
  "intent": <intent_value>,
  "slots": {},
  "confidence": <0.0–1.0>
}

## vague = true ШАРТТАРЫ:
- Тек бір тақырып сөзі, не істеу керек — белгісіз: "фридом", "дивиденд", "шот"
- Жалпы сұрақ, мақсат анық емес: "қалай?", "не істеу керек?", "помоги"
- Тақырып + қалай/как — нақты не білгісі келеді, белгісіз: "фридом қалай", "дивиденды как"
- 2+ тақырып бір сөйлемде: "шот және дивиденд"
- Тек брокер аты: "freedom broker", "tabys"

## vague = false ШАРТТАРЫ:
- Нақты объект + нақты әрекет: "екінші шот ашу" → false
- Нақты мәселе: "пополнение сколько стоит" → false
- Нақты сұрақ белгілі жауаппен: "ИИС-3 лимиті қанша" → false

## intent мәндері:
- open_account      — шот ашу, первый/второй счёт, freedom/tabys регистрация
- deposit_withdraw  — толтыру, шығару, пополнение, вывод, перевод
- stocks_bonds      — акция, облигация, ETF, сатып алу, купить
- dividends         — дивиденд, выплата
- currency          — валюта, айырбас, обмен
- commission_tariff — тариф, комиссия, ставка
- tax               — салық, налог, ИИС, ИИС-3
- portfolio         — портфель, стратегия
- greeting          — сәлем, привет, hello, қалайсың
- off_topic         — спорт, ауа-райы, медицина, саясат, тамақ, 18+
- general           — жалпы брокерлік сұрақ, басқа тақырыптарға жатпайтын

## slots (бар болса ғана толтыр):
- broker: "freedom" | "tabys"
- account_type: "first" | "second" | "ИИС" | "ИИС-3"
- asset_type: "stock" | "bond" | "etf"
- direction: "buy" | "sell" | "deposit" | "withdraw"

## Мысалдар:
Кіріс: "фридом қалай"
Шығыс: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"freedom"},"confidence":0.88}

Кіріс: "как открыть второй счёт во Freedom"
Шығыс: {"language":"ru","vague":false,"intent":"open_account","slots":{"broker":"freedom","account_type":"second"},"confidence":0.97}

Кіріс: "дивиденды"
Шығыс: {"language":"ru","vague":true,"intent":"dividends","slots":{},"confidence":0.92}

Кіріс: "облигация сатып алу қалай"
Шығыс: {"language":"kk","vague":false,"intent":"stocks_bonds","slots":{"asset_type":"bond","direction":"buy"},"confidence":0.95}

Кіріс: "сәлем"
Шығыс: {"language":"kk","vague":false,"intent":"greeting","slots":{},"confidence":0.99}

Кіріс: "табыс про"
Шығыс: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"tabys"},"confidence":0.85}

Кіріс: "ИИС-3 лимит"
Шығыс: {"language":"ru","vague":true,"intent":"tax","slots":{"account_type":"ИИС-3"},"confidence":0.87}

Кіріс: "как пополнить счёт через каспи"
Шығыс: {"language":"ru","vague":false,"intent":"deposit_withdraw","slots":{"direction":"deposit"},"confidence":0.96}

Кіріс: "футбол нәтижелері"
Шығыс: {"language":"kk","vague":false,"intent":"off_topic","slots":{},"confidence":0.99}
"""

# ─── Deterministic fallback (no LLM) ─────────────────────────────────────────

_KK_CHARS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
_RU_MARKERS = set("ёъ")
_RU_WORDS = {"как", "что", "это", "для", "или", "где", "когда", "нет", "да", "можно"}

_KK_STOP = {"қалай", "туралы", "бол", "деген", "керек", "және", "үшін", "не", "мен"}
_RU_STOP = {"как", "что", "это", "для", "или", "про", "о", "а", "и", "в", "на"}

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "open_account":      ["шот", "счет", "счёт", "ашу", "открыт", "первый", "второй",
                          "бірінші", "екінші", "регистр"],
    "deposit_withdraw":  ["толтыр", "шығар", "пополн", "вывод", "перевод", "каспи"],
    "dividends":         ["дивиденд"],
    "stocks_bonds":      ["акци", "облигац", "etf", "қор", "бумаг"],
    "currency":          ["валют", "айырбас", "обмен", "доллар", "евро", "тенге"],
    "commission_tariff": ["тариф", "комисси"],
    "tax":               ["салық", "налог", "иис"],
    "portfolio":         ["портфел", "стратег"],
    "greeting":          ["сәлем", "салем", "привет", "здравствуй", "hello", "hi"],
}


def _fallback_classify(text: str) -> ClassificationResult:
    """Детерминированный fallback — работает без LLM. confidence=0.0."""
    lower = text.lower()
    words = lower.split()

    # Язык
    if any(c in _KK_CHARS for c in text):
        lang: Literal["ru", "kk"] = "kk"
    elif any(c in _RU_MARKERS for c in lower) or len(set(words) & _RU_WORDS) >= 2:
        lang = "ru"
    else:
        lang = "kk"  # default

    # Intent
    intent: IntentType = "general"
    for intent_name, keywords in _INTENT_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            intent = intent_name  # type: ignore
            break

    # Vague — простая эвристика
    stop = _KK_STOP | _RU_STOP
    meaningful = [w for w in words if w not in stop and len(w) > 2]
    vague = len(meaningful) <= 2

    logger.warning(f"[Classifier] using deterministic fallback for: '{text[:50]}'")
    return ClassificationResult(
        language=lang,
        vague=vague,
        intent=intent,
        slots={},
        confidence=0.0,
    )


# ─── Main Classifier ──────────────────────────────────────────────────────────

class LLMClassifier:
    """
    Single-call LLM classifier.

    Заменяет:
      - LanguageDetector
      - IntentRouter
      - is_vague_query() + VAGUE_WORDS
      - classify_intent_fast()

    При любой ошибке LLM — возвращает детерминированный fallback,
    никогда не бросает исключение наружу.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model

    async def classify(self, text: str) -> ClassificationResult:
        key = _cache_key(text)

        cached = _cache_get(key)
        if cached is not None:
            logger.debug(f"[Classifier] cache hit | {text[:40]}")
            return cached

        try:
            result = await self._call_llm(text)

            # Низкий confidence → всегда vague=true (безопаснее спросить)
            if result.confidence < 0.5:
                logger.warning(
                    f"[Classifier] low confidence={result.confidence:.2f}, forcing vague=true"
                )
                result = result.model_copy(update={"vague": True})

            _cache_set(key, result)
            logger.info(
                f"[Classifier] lang={result.language} vague={result.vague} "
                f"intent={result.intent} conf={result.confidence:.2f} | '{text[:50]}'"
            )
            return result

        except Exception as e:
            logger.error(f"[Classifier] LLM error: {e!r} — using fallback")
            return _fallback_classify(text)

    async def _call_llm(self, text: str) -> ClassificationResult:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            max_tokens=150,
            response_format={"type": "json_object"},
            timeout=5.0,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        return ClassificationResult(**data)