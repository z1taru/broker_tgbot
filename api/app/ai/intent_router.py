from typing import Dict, Literal
from openai import OpenAI
import json

IntentType = Literal["greeting", "general", "faq", "unclear", "off_topic"]

class IntentRouter:
    def __init__(self):
        self.client = OpenAI()
    
    def detect_intent(self, user_question: str, language: str) -> Dict[str, any]:
        """Классификация намерения пользователя"""
        
        system_prompt = self._get_intent_system_prompt(language)
        
        user_prompt = f"""Классифицируй вопрос пользователя:
"{user_question}"

Ответь ТОЛЬКО в формате JSON:
{{
    "intent": "greeting|general|faq|unclear|off_topic",
    "confidence": 0.95,
    "extracted_keywords": ["слово1", "слово2"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            return {
                "intent": "faq",
                "confidence": 0.5,
                "extracted_keywords": []
            }
    
    def _get_intent_system_prompt(self, language: str) -> str:
        if language == "kk":
            return """Сіз инвестициялық брокерлік боттың intent классификаторысыз.

БОТ ТАҚЫРЫПТАРЫ (тек осылар):
- Шот ашу (бірінші, екінші шот, Freedom Broker, Tabys Pro)
- Толтыру және шығару (пополнение, вывод)
- Акциялар, облигациялар, ETF сатып алу/сату
- Дивидендтер
- Валюта айырбасы
- Тарифтер және комиссиялар
- Салықтар (ИИС, ИИС-3, брокерлік есеп)
- Портфель, стратегиялар
- Бот туралы сұрақтар (не істей аласың)

Intent түрлері:
- greeting: сәлем, қалайсың, салам т.б.
- general: бот не істей алады деген сұрақтар
- faq: инвестиция, брокер, шот, акция, облигация, дивиденд, тариф, салық, валюта, портфель туралы кез-келген сұрақ
- unclear: тым жалпы ("көмектес", "не істеу керек", "жұмыс істемейді") — инвестиция тақырыбына жататын болуы мүмкін
- off_topic: инвестиция, брокер, қаржы тақырыбына МҮЛДЕМ қатысы жоқ сұрақтар (ауа райы, спорт, тамақ, кино, 18+, балалар контенті, саясат, медицина, т.б.)

МАҢЫЗДЫ: Күмән болса — faq немесе unclear деп белгіле. off_topic тек айқын брокерлік тақырыптан тыс жағдайда ғана.

Жауап форматы: JSON"""
        else:
            return """Вы — intent классификатор для инвестиционного брокерского бота.

ТЕМЫ БОТА (только они):
- Открытие счета (первый, второй счет, Freedom Broker, Tabys Pro)
- Пополнение и вывод средств
- Покупка/продажа акций, облигаций, ETF
- Дивиденды
- Обмен валюты
- Тарифы и комиссии
- Налоги (ИИС, ИИС-3, брокерский счёт)
- Портфель, стратегии инвестирования
- Вопросы о боте (что умеешь)

Типы intent:
- greeting: привет, как дела, салам и т.д.
- general: вопросы о том, что умеет бот
- faq: любой вопрос об инвестициях, брокере, счёте, акциях, облигациях, дивидендах, тарифах, налогах, валюте, портфеле
- unclear: слишком общий запрос ("помоги", "что делать", "не работает") — может относиться к инвестициям
- off_topic: запросы, ПОЛНОСТЬЮ не связанные с инвестициями и брокером (погода, спорт, еда, кино, 18+, детский контент, политика, медицина и т.п.)

ВАЖНО: При сомнении — ставь faq или unclear. off_topic только когда ОЧЕВИДНО не относится к брокерской теме.

Формат ответа: JSON"""