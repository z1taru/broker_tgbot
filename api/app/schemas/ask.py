from pydantic import BaseModel, Field
from typing import Optional


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    user_id: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="auto", max_length=10)


class AskResponse(BaseModel):
    action: str
    question: str
    answer_text: Optional[str] = None
    video_url: Optional[str] = None
    faq_id: Optional[int] = None
    confidence: float
    message: Optional[str] = None