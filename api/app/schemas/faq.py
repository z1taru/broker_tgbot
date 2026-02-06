from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class FAQBase(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    answer_text: str = Field(..., min_length=1, max_length=5000)
    video_url: str | None = Field(None, max_length=500)
    category: str = Field(..., min_length=1, max_length=100)
    language: str = Field(default="kk", min_length=2, max_length=10)


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: str | None = Field(None, min_length=1, max_length=1000)
    answer_text: str | None = Field(None, min_length=1, max_length=5000)
    video_url: str | None = Field(None, max_length=500)
    category: str | None = Field(None, min_length=1, max_length=100)
    language: str | None = Field(None, min_length=2, max_length=10)


class FAQResponse(FAQBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: datetime


class CategoriesResponse(BaseModel):
    categories: list[str] = Field(..., min_items=0)