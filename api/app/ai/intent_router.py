# api/app/ai/intent_router.py
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
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            # Фоллбэк при ошибке
            return {
                "intent": "faq",
                "confidence": 0.5,
                "extracted_keywords": []
            }
    
    def _get_intent_system_prompt(self, language: str) -> str:
        if language == "kk":
            return """Сіз инвестициялық боттың intent классификаторысыз.

Intent түрлері:
- greeting: сәлем, қалайсың, салам т.б.
- general: бот туралы сұрақтар (не істей аласың, қашан жасалдың)
- faq: нақты сұрақ (шот ашу, облигация алу, валюта айырбасы)
- unclear: тым жалпы ("көмектес", "не істеу керек", "жұмыс істемейді")
- off_topic: доменнен тыс (ауа райы, футбол)

Жауап форматы: JSON"""
        else:
            return """Вы - intent классификатор для инвестиционного бота.

Типы intent:
- greeting: привет, как дела, салам и т.д.
- general: вопросы о боте (что умеешь, когда создан)
- faq: конкретный вопрос (открыть счет, купить облигации, обмен валюты)
- unclear: слишком общий ("помоги", "что делать", "не работает")
- off_topic: вне домена (погода, футбол)

Формат ответа: JSON"""