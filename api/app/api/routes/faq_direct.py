# api/app/api/routes/faq_direct.py
"""
Эндпоинт для получения прямого ответа по faq_id.
Используется ботом когда пользователь выбрал вариант из clarify-меню.
Не делает никакого поиска — просто достаёт FAQ из БД и возвращает.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.ai.search_enhanced import EnhancedSearchService
from app.schemas.ask import AskResponse
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.get("/faq-direct/{faq_id}", response_model=AskResponse)
async def get_faq_direct(
    faq_id: int,
    session: AsyncSession = Depends(get_session),
):
    """
    Вернуть прямой ответ по faq_id — без поиска, без классификации.
    Используется после того как пользователь выбрал вариант в clarify.
    """
    sql = text("""
        SELECT
            faq_v2.id,
            faq_content.question,
            faq_content.answer_text,
            faq_content.video          AS video_file_id,
            faq_v2.category,
            faq_content.language,
            faq_v2.created_at,
            faq_content.description_footer
        FROM faq_content
        INNER JOIN faq_v2 ON faq_content.faq_id = faq_v2.id
        WHERE faq_v2.id = :faq_id
          AND faq_v2.is_active = TRUE
        LIMIT 1
    """)

    result = await session.execute(sql, {"faq_id": faq_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"FAQ {faq_id} not found")

    video_url = EnhancedSearchService._build_video_url(row[3])

    answer = row[2]
    footer = row[7]
    if footer and str(footer).strip():
        answer = f"{answer}\n\n<i>{footer}</i>"

    logger.info(f"[FaqDirect] faq_id={faq_id} video={'yes' if video_url else 'no'}")

    return AskResponse(
        action="direct_answer",
        question=row[1],
        detected_language=row[5],  # язык из БД
        answer_text=answer,
        video_url=video_url,
        faq_id=row[0],
        confidence=1.0,
    )