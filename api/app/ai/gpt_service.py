# api/app/ai/gpt_service.py
from typing import List, Tuple, Dict, Any
import httpx
from openai import OpenAI
from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class GPTService:
    def __init__(self):
        http_client = httpx.Client()
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            http_client=http_client
        )
        self.model = settings.AI_MODEL
    
    async def generate_clarification(
        self,
        user_question: str,
        similar_faqs: List[Tuple[Dict[str, Any], float]],
        language: str
    ) -> str:
        """Generate clarification question when confidence is medium"""
        
        faq_list = "\n".join([
            f"- {faq['question']} (similarity: {score:.2f})"
            for faq, score in similar_faqs[:3]
        ])
        
        system_prompt = self._get_system_prompt(language)
        
        user_prompt = f"""User asked: "{user_question}"

Similar FAQs found:
{faq_list}

Generate a short clarification question to help user choose the most relevant FAQ.
Keep it concise and friendly. Use {language} language."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating clarification: {e}")
            return self._get_fallback_clarification(language)
    
    async def generate_fallback_response(
        self,
        user_question: str,
        language: str
    ) -> str:
        """Generate fallback response when no FAQ matches"""
        
        system_prompt = self._get_system_prompt(language)
        
        user_prompt = f"""User asked: "{user_question}"

No relevant FAQ found in our database.

Provide a brief, helpful response that:
1. Acknowledges the question
2. Explains we don't have specific information about this
3. Suggests contacting support for detailed help
4. Keep it short and friendly

Use {language} language."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=300
            )
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            logger.error(f"Error generating fallback: {e}")
            return self._get_fallback_message(language)
    
    def _get_system_prompt(self, language: str) -> str:
        """Get system prompt based on language"""
        if language == "kk":
            return """You are a helpful investment assistant for Kazakh-speaking users.
Your role is to help users find information about investments, brokers, and trading.
You do NOT give financial advice or investment recommendations.
You do NOT make up information.
You only help users navigate existing FAQ or connect them with support."""
        else:
            return """You are a helpful investment assistant for Russian-speaking users.
Your role is to help users find information about investments, brokers, and trading.
You do NOT give financial advice or investment recommendations.
You do NOT make up information.
You only help users navigate existing FAQ or connect them with support."""
    
    def _get_fallback_clarification(self, language: str) -> str:
        """Fallback clarification if GPT fails"""
        if language == "kk":
            return "Кешіріңіз, сұрағыңыз түсініксіз болды. Нақтырақ жазып көріңізші?"
        else:
            return "Извините, вопрос не совсем понятен. Можете уточнить?"
    
    def _get_fallback_message(self, language: str) -> str:
        """Fallback message if GPT fails"""
        if language == "kk":
            return "Кешіріңіз, сұрағыңызға жауап таппадым. Қолдау қызметіне жазыңыз."
        else:
            return "Извините, не нашёл ответа на ваш вопрос. Обратитесь в поддержку."