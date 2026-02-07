# api/app/api/routes/ask.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.ai.embeddings import EmbeddingService
from app.ai.similarity import SimilarityService
from app.ai.decision import DecisionEngine
from app.ai.gpt_service import GPTService
from app.ai.language_detector import LanguageDetector
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    AI-powered question answering endpoint
    """
    try:
        language = request.language
        if language == "auto":
            detector = LanguageDetector()
            language = detector.detect(request.question)
        
        logger.info(f"Processing question from user {request.user_id} in {language}")
        
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.create_embedding(request.question)
        
        similarity_service = SimilarityService()
        similar_faqs = await similarity_service.find_similar_faqs(
            session=session,
            query_embedding=query_embedding,
            language=language,
        )
        
        decision_engine = DecisionEngine()
        decision = decision_engine.make_decision(similar_faqs)
        
        action = decision["action"]
        
        if action == "direct_answer":
            faq = decision["faq"]
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=faq.answer_text,
                video_url=faq.video_url,
                faq_id=faq.id,
                confidence=decision["score"]
            )
        
        elif action == "clarify":
            gpt_service = GPTService()
            clarification = await gpt_service.generate_clarification(
                user_question=request.question,
                similar_faqs=decision["all_matches"],
                language=language
            )
            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=decision["score"]
            )
        
        else:
            gpt_service = GPTService()
            fallback = await gpt_service.generate_fallback_response(
                user_question=request.question,
                language=language
            )
            return AskResponse(
                action="no_match",
                question=request.question,
                message=fallback,
                confidence=decision["score"]
            )
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
