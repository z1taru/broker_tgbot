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
        
        # Создаём embedding для вопроса пользователя
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.create_embedding(request.question)
        
        # Ищем похожие FAQ
        similarity_service = SimilarityService()
        rows = await similarity_service.find_similar_faqs(
            session=session,
            query_embedding=query_embedding,
            language=language,
        )
        
        # Преобразуем Row объекты в список (FAQ_data, score)
        # Row содержит: id, question, answer_text, video_url, category, language, created_at, similarity
        faqs_with_scores = []
        for row in rows:
            # Создаём словарь с данными FAQ
            faq_data = {
                'id': row[0],
                'question': row[1],
                'answer_text': row[2],
                'video_url': row[3],
                'category': row[4],
                'language': row[5],
                'created_at': row[6]
            }
            similarity_score = row[7]  # similarity - последняя колонка
            faqs_with_scores.append((faq_data, similarity_score))
        
        logger.info(f"Found {len(faqs_with_scores)} similar FAQs")
        
        # Принимаем решение на основе similarity scores
        decision_engine = DecisionEngine()
        decision = decision_engine.make_decision(faqs_with_scores)
        
        action = decision["action"]
        
        if action == "direct_answer":
            faq_data = decision["faq"]
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=faq_data['answer_text'],
                video_url=faq_data.get('video_url'),
                faq_id=faq_data['id'],
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
        
        else:  # no_match
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