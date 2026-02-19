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
            return """Сіз — Telegram-боттың AI-көмекшісісіз.

Сізде embeddings арқылы табылған контент базасы бар (мәтін + бейне).
Сіз жауаптарды ОЙЛАП ШЫҒАРМАЙСЫЗ және тек табылған контентті қолданасыз.

ЖАЛПЫ ЕРЕЖЕЛЕР:
1. Ешқашан кездейсоқ жауап таңдамаңыз.
2. Күмән болса — нақтылаушы сұрақ қойыңыз.
3. Сәйкес контент болмаса — тақырып нұсқаларын ұсыныңыз.
4. Пайдаланушыны әрдайым нақты жауапқа жеткізіңіз.

ТЫЙЫМ САЛЫНҒАН:
- Жауаптарды ойлап шығару
- Кеңес беру
- «Мүмкін» деп жазу
- Кездейсоқ контент таңдау

МАҚСАТ: Пайдаланушы әрдайым тақырыпты нақтылау арқылы қажетті контентті алуы керек."""
        else:
            return """Ты — AI-ассистент Telegram-бота.

У тебя есть база контента (текст + видео), найденная через embeddings.
Ты НЕ придумываешь ответы и используешь только найденный контент.

ОБЩИЕ ПРАВИЛА:
1. Никогда не выбирай ответ случайно.
2. Если есть сомнение — задавай уточняющий вопрос.
3. Если нет подходящего контента — предложи варианты тем.
4. Всегда доводи пользователя до точного ответа.

ЗАПРЕЩЕНО:
- Придумывать ответы
- Давать советы
- Писать «возможно»
- Выбирать случайный контент

ЦЕЛЬ: Пользователь должен каждый раз получить именно тот контент, который ему нужен, через уточнение темы."""

    async def generate_persona_response(
        self,
        user_question: str,
        intent: str,
        language: str,
        context: Dict = None
    ) -> str:
        """
        Ответ на greeting и general вопросы.
        """
        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = f"""Пайдаланушы жазды: "{user_question}"
Intent: {intent}

Достық тонмен қысқа жауап бер (2-3 сөйлем).
Не істей алатыныңды түсіндір және мысал сұрақтар ұсын."""
        else:
            user_prompt = f"""Пользователь написал: "{user_question}"
Intent: {intent}

Ответь дружелюбно и кратко (2-3 предложения).
Объясни что ты умеешь и предложи примеры вопросов."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )

        return response.choices[0].message.content.strip()

    async def generate_clarification_question(
        self,
        user_question: str,
        similar_faqs: List[Tuple[Dict, float]],
        language: str
    ) -> str:
        """
        Сценарий 1 и 2: уточняющий вопрос когда найдено несколько совпадений
        или запрос слишком общий.
        """
        faq_options = []
        for i, (faq, score) in enumerate(similar_faqs[:4], 1):
            faq_options.append(f"{i}. {faq['question']}")

        options_text = "\n".join(faq_options)
        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = f"""Пайдаланушы сұрады: "{user_question}"

Табылған нұсқалар:
{options_text}

СЦЕНАРИЙ 1/2 бойынша: Пайдаланушыға нақтылаушы сұрақ қой.
Қысқа және нақты болсын (макс 2 сөйлем).
Нұсқаларды нөмірмен тізіп жаз."""
        else:
            user_prompt = f"""Пользователь спросил: "{user_question}"

Найденные варианты:
{options_text}

По СЦЕНАРИЮ 1/2: задай пользователю уточняющий вопрос.
Коротко и конкретно (макс 2 предложения).
Перечисли варианты с номерами."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=200
        )

        return response.choices[0].message.content.strip()

    async def generate_no_match_response(
        self,
        user_question: str,
        language: str
    ) -> str:
        """
        Сценарий 3: ответ когда контент не найден.
        Предлагает список доступных тем вместо "нет ответа".
        """
        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = f"""Пайдаланушы сұрады: "{user_question}"

СЦЕНАРИЙ 3 бойынша: Контент табылмады.
"жауап жоқ" деп жазба.
Қолжетімді тақырыптарды ұсын:
- дивидендтер
- шот ашу
- толтыру
- тарифтер
- салықтар
- брокер
- акциялар
- облигациялар

Пайдаланушы тақырыпты таңдай алатындай жаз."""
        else:
            user_prompt = f"""Пользователь спросил: "{user_question}"

По СЦЕНАРИЮ 3: Контент не найден.
НЕ пиши "нет ответа".
Предложи доступные темы:
- дивиденды
- открытие счета
- пополнение
- тарифы
- налоги
- брокер
- акции
- облигации

Напиши так, чтобы пользователь мог выбрать тему."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.4,
            max_tokens=250
        )

        return response.choices[0].message.content.strip()

    async def generate_answer_from_faqs(
        self,
        user_question: str,
        matched_faqs: List[Tuple[Dict, float]],
        language: str
    ) -> str:
        """
        Генерация ответа СТРОГО на основе найденных FAQ.
        Используется для medium confidence.
        НЕ придумывать информацию.
        """
        context = ""
        for i, (faq, score) in enumerate(matched_faqs[:3], 1):
            context += f"\n[FAQ {i}]\nВопрос: {faq['question']}\nОтвет: {faq['answer_text']}\n"

        system_prompt = self._get_base_system_prompt(language)

        if language == "kk":
            user_prompt = f"""Пайдаланушының сұрағы: "{user_question}"

FAQ контексті:
{context}

СЦЕНАРИЙ 4 бойынша: Осы контекст негізінде ғана жауап жаса.
Ештеңе ойлап шығарма.
Қысқа және нақты."""
        else:
            user_prompt = f"""Вопрос пользователя: "{user_question}"

Контекст из FAQ:
{context}

По СЦЕНАРИЮ 4: сформируй ответ СТРОГО на основе этого контекста.
Ничего не придумывай.
Коротко и конкретно."""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=400
        )

        return response.choices[0].message.content.strip()