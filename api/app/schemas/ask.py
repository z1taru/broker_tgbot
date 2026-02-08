# api/app/schemas/ask.py
from pydantic import BaseModel, Field
from typing import Optional, List


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    user_id: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="auto", max_length=10)


class AskResponse(BaseModel):
    action: str  # "direct_answer" | "clarify" | "show_similar" | "no_match"
    question: str
    
    # Для прямого ответа
    answer_text: Optional[str] = None
    video_url: Optional[str] = None
    faq_id: Optional[int] = None
    
    # Для других сценариев
    message: Optional[str] = None
    
    # НОВОЕ: список предложений (для UI)
    suggestions: Optional[List[str]] = None
    
    confidence: float