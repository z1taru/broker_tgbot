# api/app/api/routes/ask_v2.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.services.rag_pipeline import RAGPipeline
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

@router.post("/ask/v2", response_model=AskResponse)
async def ask_question_v2(
    request: AskRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Enhanced AI-powered question answering с RAG pipeline
    """
    pipeline = RAGPipeline()
    
    result = await pipeline.process_query(
        session=session,
        user_question=request.question,
        language=request.language,
        use_cache=True,
        use_rerank=True
    )
    
    if not result['results']:
        return AskResponse(
            action="no_match",
            question=request.question,
            message="К сожалению, не нашел ответа. Обратитесь в поддержку.",
            confidence=0.0
        )
    
    # Берем топ результат
    top_result = result['results'][0]
    
    if top_result['score'] >= 0.75:
        return AskResponse(
            action="direct_answer",
            question=request.question,
            answer_text=top_result['answer'],
            video_url=top_result['video_url'],
            faq_id=top_result['faq_id'],
            confidence=top_result['score']
        )
    elif top_result['score'] >= 0.5:
        # Показать несколько вариантов
        options = "\n".join([
            f"{i+1}. {r['question']}"
            for i, r in enumerate(result['results'][:3])
        ])
        return AskResponse(
            action="clarify",
            question=request.question,
            message=f"Уточните вопрос. Возможно вы имели в виду:\n{options}",
            confidence=top_result['score']
        )
    else:
        return AskResponse(
            action="no_match",
            question=request.question,
            message="Не нашел точного ответа. Попробуйте переформулировать.",
            confidence=top_result['score']
        )