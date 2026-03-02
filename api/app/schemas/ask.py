# api/app/schemas/ask.py
from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    user_id: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="auto", max_length=10)


class AskResponse(BaseModel):
    action: str  # "direct_answer" | "clarify" | "show_similar" | "no_match"
    question: str

    # Язык определённый LLM classifier — бот использует для UI
    detected_language: Optional[Literal["ru", "kk"]] = "kk"

    # Прямой ответ
    answer_text: Optional[str] = None
    video_url: Optional[str] = None
    faq_id: Optional[int] = None

    # Clarify / show_similar
    message: Optional[str] = None
    suggestions: Optional[List[str]] = None      # тексты вариантов (для отображения)
    suggestion_ids: Optional[List[int]] = None   # faq_id для каждого варианта

    confidence: float