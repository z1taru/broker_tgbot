# api/app/ai/gpt_service.py
from typing import List, Tuple, Dict, Any
from openai import OpenAI
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GPTService:
    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-4o-mini"

    def _get_base_system_prompt(self, language: str) -> str:
        if language == "kk":
            return """Сіз — инвестициялық брокерлік Telegram-боттың AI-көмекшісісіз.

МАҢЫЗДЫ: Барлық жауаптарды ТЕК ҚАЗАҚ ТІЛІНДЕ жаз.

ҚАТАҢ ШЕКТЕУЛЕР:
1. Тек мына тақырыптар бойынша жауап бер:
   - Шот ашу (Freedom Broker, Tabys Pro, бірінші/екінші шот)
   - Толтыру және шығару
   - Акциялар, облигациялар, ETF
   - Дивидендтер
   - Валюта айырбасы
   - Тарифтер және комиссиялар
   - Салықтар (ИИС, ИИС-3)
   - Портфель және стратегиялар

2. БАС ТАРТУ КЕРЕК:
   - 18+ мазмұн, балалар мазмұны
   - Саясат, дін, спорт, ауа райы
   - Медицина, заң кеңесі
   - Брокерлік тақырыптан тыс кез-келген нәрсе

3. Ешқашан ойлап шығарма — тек табылған контентті қолдан

4. Брокерлік тақырып болмаса:
   "Мен тек инвестициялар мен брокерлік қызметтер туралы сұрақтарға жауап беремін." """
        else:
            return """Вы — AI-ассистент Telegram-бота инвестиционного брокера.

ВАЖНО: Все ответы пишите ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.
ВАЖНО: Контекст из FAQ может быть на казахском — это нормально.
Твоя задача — понять смысл казахского контекста и передать его НА РУССКОМ.

СТРОГИЕ ОГРАНИЧЕНИЯ:
1. Отвечай ТОЛЬКО по этим темам:
   - Открытие счёта (Freedom Broker, Tabys Pro, первый/второй счёт)
   - Пополнение и вывод средств
   - Акции, облигации, ETF
   - Дивиденды
   - Обмен валюты
   - Тарифы и комиссии
   - Налоги (ИИС, ИИС-3)
   - Портфель и стратегии

2. ОТКАЗЫВАЙ:
   - 18+ контент, детский контент
   - Политика, религия, спорт, погода
   - Медицина, юридические советы
   - Всё вне брокерской тематики

3. Никогда не придумывай — только найденный контент

4. Если тема НЕ брокерская:
   "Я отвечаю только на вопросы об инвестициях и брокерских услугах." """

    def get_off_topic_response(self, language: str) -> str:
        if language == "kk":
            return (
                "💼 Мен тек инвестициялар мен брокерлік қызметтер туралы сұрақтарға жауап беремін.\n\n"
                "Мысалы:\n"
                "• Шот қалай ашамыз?\n"
                "• Облигация қалай аламыз?\n"
                "• Дивидендтер қалай есептеледі?\n"
                "• Валюта айырбасы\n\n"
                "Инвестициялар туралы сұрағыңыз болса — жазыңыз! 📊"
            )
        else:
            return (
                "💼 Я отвечаю только на вопросы об инвестициях и брокерских услугах.\n\n"
                "Например:\n"
                "• Как открыть счёт?\n"
                "• Как купить облигацию?\n"
                "• Как начисляются дивиденды?\n"
                "• Обмен валюты\n\n"
                "Если есть вопрос об инвестициях — спрашивайте! 📊"
            )

    async def generate_persona_response(
        self,
        user_question: str,
        intent: str,
        language: str,
        context: Dict = None,
    ) -> str:
        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = (
                f'Пайдаланушы жазды: "{user_question}"\n'
                f"Intent: {intent}\n\n"
                "МІНДЕТТІ: Тек қазақша жауап бер.\n"
                "Достық тонмен қысқа жауап бер (2-3 сөйлем).\n"
                "Не істей алатыныңды түсіндір — тек инвестиция/брокер тақырыптары.\n"
                "Мысал сұрақтар ұсын (тек брокерлік тақырыптан)."
            )
        else:
            user_prompt = (
                f'Пользователь написал: "{user_question}"\n'
                f"Intent: {intent}\n\n"
                "ОБЯЗАТЕЛЬНО: Отвечай только на русском языке.\n"
                "Ответь дружелюбно и кратко (2-3 предложения).\n"
                "Объясни что умеешь — только инвестиции и брокерские услуги.\n"
                "Предложи примеры вопросов (только по брокерской теме)."
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
        return response.choices[0].message.content.strip()

    async def generate_clarification_question(
        self,
        user_question: str,
        similar_faqs: List[Tuple[Dict, float]],
        language: str,
    ) -> str:
        # Варианты всегда на казахском (из БД) — показываем как есть
        # GPT генерирует только вводный текст на нужном языке
        faq_options = "\n".join(
            f"{i}. {faq['question']}"
            for i, (faq, _) in enumerate(similar_faqs[:4], 1)
        )
        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = (
                f'Пайдаланушы сұрады: "{user_question}"\n\n'
                f"Табылған нұсқалар:\n{faq_options}\n\n"
                "МІНДЕТТІ: Жауабыңды ТЕК ҚАЗАҚ ТІЛІНДЕ жаз.\n"
                "Нақтылаушы сұрақ қой қазақша. Нұсқаларды нөмірмен тізіп жаз.\n"
                "Максималды 2 сөйлем."
            )
        else:
            user_prompt = (
                f'Пользователь спросил: "{user_question}"\n\n'
                f"Найденные варианты (на казахском — это контент из базы):\n{faq_options}\n\n"
                "ОБЯЗАТЕЛЬНО: Пиши вводный текст ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.\n"
                "Задай уточняющий вопрос на русском. Варианты не перечисляй — они будут показаны отдельно.\n"
                "Максимум 1-2 предложения."
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=200,
        )
        result = response.choices[0].message.content.strip()

        if language == "kk" and not self._has_kazakh_chars(result):
            logger.warning("[GPTService] GPT returned non-Kazakh clarification, using template")
            result = self._clarification_template_kk(similar_faqs)

        return result

    def _has_kazakh_chars(self, text: str) -> bool:
        kazakh_chars = set("әіңғүұқөһӘІҢҒҮҰҚӨҺ")
        kazakh_words = {"сіз", "мен", "бұл", "қалай", "және", "немесе"}
        return any(c in kazakh_chars for c in text) or any(w in text.lower() for w in kazakh_words)

    def _clarification_template_kk(self, similar_faqs: List[Tuple[Dict, float]]) -> str:
        options = "\n".join(
            f"{i}. {faq['question']}"
            for i, (faq, _) in enumerate(similar_faqs[:4], 1)
        )
        return f"Сіз нені білгіңіз келеді?\n\n{options}"

    async def generate_no_match_response(
        self,
        user_question: str,
        language: str,
    ) -> str:
        if language == "kk":
            return (
                "💡 Осы тақырып бойынша ақпарат табылмады.\n\n"
                "Мен жауап бере алатын тақырыптар:\n"
                "• Шот ашу (бірінші/екінші шот)\n"
                "• Толтыру және шығару\n"
                "• Акциялар және облигациялар\n"
                "• Дивидендтер\n"
                "• Валюта айырбасы\n"
                "• Тарифтер және комиссиялар\n"
                "• Салықтар (ИИС, ИИС-3)\n\n"
                "Осы тақырыптардың бірі бойынша сұрақ қойыңыз 📊"
            )
        else:
            return (
                "💡 По этой теме информация не найдена.\n\n"
                "Темы, по которым я могу помочь:\n"
                "• Открытие счёта (первый/второй счёт)\n"
                "• Пополнение и вывод средств\n"
                "• Акции и облигации\n"
                "• Дивиденды\n"
                "• Обмен валюты\n"
                "• Тарифы и комиссии\n"
                "• Налоги (ИИС, ИИС-3)\n\n"
                "Задайте вопрос по одной из этих тем 📊"
            )

    async def generate_answer_from_faqs(
        self,
        user_question: str,
        matched_faqs: List[Tuple[Dict, float]],
        language: str,
    ) -> str:
        # Контекст из БД на казахском — передаём как есть
        context = ""
        for i, (faq, score) in enumerate(matched_faqs[:3], 1):
            context += f"\n[FAQ {i}]\nВопрос: {faq['question']}\nОтвет: {faq['answer_text']}\n"

        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = (
                f'Пайдаланушының сұрағы: "{user_question}"\n\n'
                f"FAQ контексті:\n{context}\n\n"
                "МІНДЕТТІ: Жауабыңды ТЕК ҚАЗАҚ ТІЛІНДЕ жаз.\n"
                "ТЕК осы контекст негізінде жауап жаса. Ештеңе ойлап шығарма.\n"
                "Қысқа және нақты. Контекст сәйкес келмесе — 'Нақтырақ сұрақ қойыңыз' деп жаз."
            )
        else:
            user_prompt = (
                f'Вопрос пользователя: "{user_question}"\n\n'
                f"Контекст из FAQ (на казахском языке — переведи смысл на русский):\n{context}\n\n"
                "ОБЯЗАТЕЛЬНО: Отвечай ТОЛЬКО НА РУССКОМ ЯЗЫКЕ.\n"
                "Контекст на казахском — прочитай его, пойми смысл и передай ответ на русском.\n"
                "Сформируй ответ СТРОГО на основе контекста. Ничего не придумывай.\n"
                "Коротко и конкретно. Если контекст не подходит — напиши 'Уточните вопрос'."
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        return response.choices[0].message.content.strip()