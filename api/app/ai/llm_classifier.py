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
    "open_account",
    "deposit_withdraw",
    "stocks_bonds",
    "dividends",
    "currency",
    "commission_tariff",
    "tax",
    "portfolio",
    "greeting",
    "off_topic",
    "general",
]


class ClassificationResult(BaseModel):
    language: Literal["ru", "kk"]
    vague: bool
    intent: IntentType
    slots: dict
    confidence: float

    @field_validator("confidence")
    @classmethod
    def clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# ─── In-memory cache ──────────────────────────────────────────────────────────

_intent_cache: dict[str, tuple[ClassificationResult, float]] = {}
_CACHE_TTL = 3600
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

## ТІЛ АНЫҚТАУ (language) — ЕҢ МАҢЫЗДЫ БӨЛІМ:

Қазақ тілі (kk) деп белгіле егер:
- Қазақша спецсимволдар болса: ә і ң ғ ү ұ қ ө һ
- Казахские слова написаны ОБЫЧНОЙ кириллицей без спецсимволов:
  деген, туралы, қалай (калай), керек, болады, айтшы, жасау,
  үшін (ушін), немесе, және, қандай (кандай), қайда (кайда),
  ашу, алу, сату, беру, көру (кору), жазу, білу (білем),
  бар, жоқ (жок), болды, болса, мына, осы, сол, бұл (бул),
  менің, сенің, оның, бізге, маған, саған,
  -да/-де/-та/-те (фридомда, табыста, шотта),
  -нан/-нен/-дан/-ден (фридомнан, шоттан),
  -ға/-ге/-қа/-ке (шотқа, фридомға),
  -ды/-ді/-ты/-ті (алды, берді, ашты),
  -мын/-мін/-пын/-пін (аламын, беремін),
  -сың/-сін (аласың, бересің),
  -лар/-лер/-дар/-дер/-тар/-тер (акциялар, шоттар)
- Казахские вопросительные слова: не (что), кім (кто), қай (который),
  қайда (где), қашан (когда), неше (сколько), қанша (сколько)
- Слово "не" в значении "что" — это казахское слово, НЕ русское отрицание

Русский язык (ru) деп белгіле егер:
- Явно русские слова: как, что, где, когда, почему, нет, да, можно,
  хочу, нужно, открыть, купить, продать, вывести, пополнить,
  счёт/счет, деньги, акции, облигации, дивиденды
- Нет ни одного казахского маркера выше

МАҢЫЗДЫ ЕРЕЖЕЛЕР:
- "деген не" → kk (деген = казахское слово, не = казахское "что")
- "фридомда купон" → kk (фридомда = казахский местный падеж -да)
- "фридом дивидент туралы" → kk (туралы = казахское слово)
- "как вывести" → ru
- "фридом как" → ru (нет казахских маркеров, "как" = русское)
- "freedom broker" → kk (default для продукта)
- Если непонятно — ставь kk (казахский — язык по умолчанию продукта)

## vague АНЫҚТАУ:

vague = true (размытый, нужно уточнение):
- Только название без действия: "фридом", "дивиденд", "шот", "табыс"
- Тема + вопрос "туралы/о/про" без конкретики: "фридом туралы", "дивиденд туралы"
- "деген не" / "что такое" — общее определение, нужно уточнить аспект
- "айтшы" без конкретики — "расскажи" без указания что именно
- Два и более топика сразу: "шот және дивиденд"

vague = false (конкретный запрос, идём в поиск):
- Конкретное место + объект: "фридомда купон" → где смотреть купон во Freedom
- Конкретное действие: "екінші шот ашу", "ақша шығару", "облигация сатып алу"
- Конкретный вопрос: "ИИС-3 лимиті қанша", "комиссия неше процент"
- Конкретная проблема: "облигация алынбай жатыр", "пополнение не проходит"
- "фридомда купон қайда" → false (конкретно: где в Freedom купон)
- "фридом дивидент туралы айтшы" → true (туралы айтшы = расскажи в общем)

## intent мәндері:
- open_account      — шот ашу, первый/второй счёт, регистрация
- deposit_withdraw  — толтыру, шығару, пополнение, вывод
- stocks_bonds      — акция, облигация, ETF
- dividends         — дивиденд, купон, выплата
- currency          — валюта, айырбас, обмен
- commission_tariff — тариф, комиссия
- tax               — салық, налог, ИИС, ИИС-3
- portfolio         — портфель, стратегия
- greeting          — сәлем, привет, hello
- off_topic         — спорт, погода, медицина, политика, еда, 18+
- general           — общий брокерский вопрос

## slots (только если явно присутствует):
- broker: "freedom" | "tabys"
- account_type: "first" | "second" | "ИИС" | "ИИС-3"
- asset_type: "stock" | "bond" | "etf"
- direction: "buy" | "sell" | "deposit" | "withdraw"

## ПРИМЕРЫ (выучи все):

Вход: "фридом қалай"
Выход: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"freedom"},"confidence":0.88}

Вход: "фридом деген не"
Выход: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"freedom"},"confidence":0.92}

Вход: "фридомда купон"
Выход: {"language":"kk","vague":false,"intent":"dividends","slots":{"broker":"freedom"},"confidence":0.91}

Вход: "фридомда купон қайда"
Выход: {"language":"kk","vague":false,"intent":"dividends","slots":{"broker":"freedom"},"confidence":0.95}

Вход: "фридом дивидент туралы айтшы"
Выход: {"language":"kk","vague":true,"intent":"dividends","slots":{"broker":"freedom"},"confidence":0.87}

Вход: "фридом туралы"
Выход: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"freedom"},"confidence":0.90}

Вход: "табыста екінші шот ашу"
Выход: {"language":"kk","vague":false,"intent":"open_account","slots":{"broker":"tabys","account_type":"second"},"confidence":0.96}

Вход: "шоттан ақша шығару"
Выход: {"language":"kk","vague":false,"intent":"deposit_withdraw","slots":{"direction":"withdraw"},"confidence":0.95}

Вход: "дивиденд"
Выход: {"language":"ru","vague":true,"intent":"dividends","slots":{},"confidence":0.85}

Вход: "дивиденд туралы"
Выход: {"language":"kk","vague":true,"intent":"dividends","slots":{},"confidence":0.88}

Вход: "как открыть второй счёт во Freedom"
Выход: {"language":"ru","vague":false,"intent":"open_account","slots":{"broker":"freedom","account_type":"second"},"confidence":0.97}

Вход: "как вывести деньги"
Выход: {"language":"ru","vague":false,"intent":"deposit_withdraw","slots":{"direction":"withdraw"},"confidence":0.95}

Вход: "облигация сатып алу қалай"
Выход: {"language":"kk","vague":false,"intent":"stocks_bonds","slots":{"asset_type":"bond","direction":"buy"},"confidence":0.95}

Вход: "ИИС-3 лимит"
Выход: {"language":"ru","vague":true,"intent":"tax","slots":{"account_type":"ИИС-3"},"confidence":0.87}

Вход: "сәлем"
Выход: {"language":"kk","vague":false,"intent":"greeting","slots":{},"confidence":0.99}

Вход: "привет"
Выход: {"language":"ru","vague":false,"intent":"greeting","slots":{},"confidence":0.99}

Вход: "табыс про"
Выход: {"language":"kk","vague":true,"intent":"general","slots":{"broker":"tabys"},"confidence":0.85}

Вход: "купон қайдан көремін"
Выход: {"language":"kk","vague":false,"intent":"dividends","slots":{},"confidence":0.94}

Вход: "пополнение как сделать"
Выход: {"language":"ru","vague":false,"intent":"deposit_withdraw","slots":{"direction":"deposit"},"confidence":0.93}

Вход: "футбол нәтижелері"
Выход: {"language":"kk","vague":false,"intent":"off_topic","slots":{},"confidence":0.99}

Вход: "фридомнан облигация алу"
Выход: {"language":"kk","vague":false,"intent":"stocks_bonds","slots":{"broker":"freedom","asset_type":"bond","direction":"buy"},"confidence":0.95}
"""


# ─── Deterministic fallback ───────────────────────────────────────────────────

_KK_CHARS = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
_RU_MARKERS = set("ёъ")
_RU_WORDS = {"как", "что", "это", "для", "или", "где", "когда", "нет", "да", "можно", "хочу"}

# Казахские слова написанные обычной кириллицей
_KK_CONTEXT_WORDS = {
    "деген", "туралы", "керек", "болады", "айтшы", "жасау",
    "алу", "беру", "ашу", "сату", "және", "немесе", "қалай",
    "калай", "кандай", "кайда", "жок", "бул", "осы", "мына",
    "аламын", "беремін", "аласын", "бересін",
}

# Казахские падежные окончания
_KK_SUFFIXES = (
    "да", "де", "та", "те",
    "дан", "ден", "тан", "тен", "нан", "нен",
    "ға", "ге", "қа", "ке",
    "ды", "ді", "ты", "ті",
    "мын", "мін", "пын", "пін",
    "лар", "лер", "дар", "дер", "тар", "тер",
    "дың", "нің", "тың",
)

_INTENT_KEYWORDS: dict[str, list[str]] = {
    "open_account":      ["шот", "счет", "счёт", "ашу", "открыт", "первый", "второй", "бірінші", "екінші"],
    "deposit_withdraw":  ["толтыр", "шығар", "пополн", "вывод", "перевод", "каспи"],
    "dividends":         ["дивиденд", "купон"],
    "stocks_bonds":      ["акци", "облигац", "etf", "қор", "бумаг"],
    "currency":          ["валют", "айырбас", "обмен", "доллар", "евро", "тенге"],
    "commission_tariff": ["тариф", "комисси"],
    "tax":               ["салық", "налог", "иис"],
    "portfolio":         ["портфел", "стратег"],
    "greeting":          ["сәлем", "салем", "привет", "здравствуй", "hello", "hi"],
}

_KK_STOP = {"қалай", "туралы", "деген", "керек", "және", "үшін", "не", "мен", "айтшы"}
_RU_STOP = {"как", "что", "это", "для", "или", "про", "о", "а", "и", "в", "на"}


def _is_kazakh_by_context(text: str) -> bool:
    """Определяет казахский язык по контексту без спецсимволов."""
    lower = text.lower()
    words = lower.split()

    # Казахские контекстные слова
    if any(w in _KK_CONTEXT_WORDS for w in words):
        return True

    # Казахские падежные окончания
    for word in words:
        for suffix in _KK_SUFFIXES:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return True

    return False


def _fallback_classify(text: str) -> ClassificationResult:
    """Детерминированный fallback без LLM. confidence=0.0."""
    lower = text.lower()
    words = lower.split()

    # Язык
    if any(c in _KK_CHARS for c in text):
        lang: Literal["ru", "kk"] = "kk"
    elif _is_kazakh_by_context(text):
        lang = "kk"
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

    # Vague
    stop = _KK_STOP | _RU_STOP
    meaningful = [w for w in words if w not in stop and len(w) > 2]
    vague = len(meaningful) <= 2

    logger.warning(f"[Classifier] deterministic fallback for: '{text[:50]}'")
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
    LLM-based classifier. Определяет язык по контексту — понимает казахский
    написанный обычной кириллицей без спецсимволов.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI()
        self.model = model

    async def classify(self, text: str) -> ClassificationResult:
        key = _cache_key(text)
        cached = _cache_get(key)
        if cached is not None:
            logger.debug(f"[Classifier] cache hit | '{text[:40]}'")
            return cached

        try:
            result = await self._call_llm(text)

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