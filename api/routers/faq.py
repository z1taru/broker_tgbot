from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

# ИСПРАВЛЕНИЕ: абсолютные импорты
from database import get_session
from models import FAQ


router = APIRouter(prefix="/faq", tags=["FAQ"])


# Pydantic схемы
class FAQResponse(BaseModel):
    id: int
    question: str
    answer_text: str
    video_url: str | None
    category: str
    language: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class CategoriesResponse(BaseModel):
    categories: List[str]


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(session: AsyncSession = Depends(get_session)):
    """Получить список всех категорий"""
    query = select(FAQ.category).distinct()
    result = await session.execute(query)
    categories = [row[0] for row in result.all()]
    return {"categories": categories}


@router.get("/category/{category}", response_model=List[FAQResponse])
async def get_faq_by_category(
    category: str,
    session: AsyncSession = Depends(get_session)
):
    """Получить все FAQ по категории"""
    query = select(FAQ).where(FAQ.category == category)
    result = await session.execute(query)
    faqs = result.scalars().all()
    
    if not faqs:
        raise HTTPException(status_code=404, detail="Category not found")
    
    return faqs


@router.get("/{faq_id}", response_model=FAQResponse)
async def get_faq_by_id(
    faq_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Получить FAQ по ID"""
    query = select(FAQ).where(FAQ.id == faq_id)
    result = await session.execute(query)
    faq = result.scalar_one_or_none()
    
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    
    return faq