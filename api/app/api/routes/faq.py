from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.repositories.faq_repository import FAQRepository
from app.schemas.faq import FAQResponse, FAQCreate, FAQUpdate, CategoriesResponse
from app.schemas.responses import APIResponse
from app.core.exceptions import NotFoundException
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/categories", response_model=CategoriesResponse)
async def get_categories(
    language: str = Query(default="kk", min_length=2, max_length=10),
    session: AsyncSession = Depends(get_session)
):
    """
    Получить список всех категорий FAQ
    """
    repo = FAQRepository(session)
    categories = await repo.get_all_categories(language=language)
    
    logger.info(f"Retrieved {len(categories)} categories for language '{language}'")
    return CategoriesResponse(categories=categories)


@router.get("/category/{category}", response_model=List[FAQResponse])
async def get_faq_by_category(
    category: str,
    language: str = Query(default="kk", min_length=2, max_length=10),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    session: AsyncSession = Depends(get_session)
):
    """
    Получить все FAQ по категории
    """
    repo = FAQRepository(session)
    faqs = await repo.get_by_category(
        category=category,
        language=language,
        skip=skip,
        limit=limit
    )
    
    if not faqs:
        raise NotFoundException(
            message=f"FAQ для категории '{category}' не найдены",
            details={"category": category, "language": language}
        )
    
    logger.info(f"Retrieved {len(faqs)} FAQs for category '{category}'")
    return faqs


@router.get("/{faq_id}", response_model=FAQResponse)
async def get_faq_by_id(
    faq_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Получить FAQ по ID
    """
    repo = FAQRepository(session)
    faq = await repo.get_by_id(faq_id)
    
    if not faq:
        raise NotFoundException(
            message=f"FAQ с ID {faq_id} не найден",
            details={"faq_id": faq_id}
        )
    
    logger.info(f"Retrieved FAQ with id={faq_id}")
    return faq


@router.post("/", response_model=FAQResponse, status_code=201)
async def create_faq(
    faq_data: FAQCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Создать новый FAQ
    """
    repo = FAQRepository(session)
    faq = await repo.create(faq_data.model_dump())
    
    logger.info(f"Created new FAQ with id={faq.id}")
    return faq


@router.put("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: int,
    faq_data: FAQUpdate,
    session: AsyncSession = Depends(get_session)
):
    """
    Обновить FAQ
    """
    repo = FAQRepository(session)
    
    if not await repo.exists(faq_id):
        raise NotFoundException(
            message=f"FAQ с ID {faq_id} не найден",
            details={"faq_id": faq_id}
        )
    
    faq = await repo.update(faq_id, faq_data.model_dump(exclude_unset=True))
    
    logger.info(f"Updated FAQ with id={faq_id}")
    return faq


@router.delete("/{faq_id}", status_code=204)
async def delete_faq(
    faq_id: int,
    session: AsyncSession = Depends(get_session)
):
    """
    Удалить FAQ
    """
    repo = FAQRepository(session)
    
    if not await repo.exists(faq_id):
        raise NotFoundException(
            message=f"FAQ с ID {faq_id} не найден",
            details={"faq_id": faq_id}
        )
    
    await repo.delete(faq_id)
    logger.info(f"Deleted FAQ with id={faq_id}")


@router.get("/stats/overview")
async def get_faq_stats(
    session: AsyncSession = Depends(get_session)
):
    """
    Получить статистику по FAQ
    """
    repo = FAQRepository(session)
    stats = await repo.get_stats()
    
    return APIResponse(
        success=True,
        data=stats,
        message="Статистика успешно получена"
    )