# api/app/api/routes/ask.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.core.logging_config import get_logger

from app.ai.intent_router import IntentRouter
from app.ai.gpt_service import GPTService
from app.ai.embeddings_enhanced import EmbeddingService
from app.ai.search_enhanced import EnhancedSearchService
from app.ai.language_detector import LanguageDetector
from app.ai.decision import DecisionEngine

logger = get_logger(__name__)
router = APIRouter()

@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    CONVERSATIONAL RAG - живой диалоговый бот
    """
    try:
        # 1. Language detection
        language = request.language
        if language == "auto":
            detector = LanguageDetector()
            language = detector.detect(request.question)
        
        logger.info(f"🔍 Question: '{request.question}' | Lang: {language}")
        
        # 2. Intent Classification
        intent_router = IntentRouter()
        intent_result = intent_router.detect_intent(request.question, language)
        
        intent = intent_result["intent"]
        logger.info(f"🎯 Intent: {intent} (confidence: {intent_result['confidence']:.2f})")
        
        # 3. Обработка по интенту
        gpt_service = GPTService()
        
        # === GREETING ===
        if intent == "greeting":
            response_text = await gpt_service.generate_persona_response(
                user_question=request.question,
                intent="greeting",
                language=language
            )
            
            # Добавляем варианты популярных вопросов
            if language == "kk":
                response_text += "\n\n💡 Мысалы:\n• Шот қалай ашамыз?\n• Облигация қалай аламыз?\n• Валюта айырбасы"
            else:
                response_text += "\n\n💡 Например:\n• Как открыть счет?\n• Как купить облигацию?\n• Обмен валюты"
            
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=response_text,
                confidence=1.0
            )
        
        # === GENERAL ===
        elif intent == "general":
            response_text = await gpt_service.generate_persona_response(
                user_question=request.question,
                intent="general",
                language=language
            )
            
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=response_text,
                confidence=0.9
            )
        
        # === OFF_TOPIC ===
        elif intent == "off_topic":
            if language == "kk":
                response_text = "Кешіріңіз, мен тек инвестициялар бойынша көмектесемін 📊\n\nСұрағыңыз:\n• Шот ашу\n• Облигация/акция алу\n• Валюта айырбасы\n\nБасқа тақырып бойынша куратор қызметіне жазыңыз"
            else:
                response_text = "Извините, я помогаю только по инвестициям 📊\n\nМогу помочь с:\n• Открытие счетов\n• Покупка облигаций/акций\n• Обмен валюты\n\nПо другим вопросам пишите куратору"
            
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=response_text,
                confidence=1.0
            )
        
        # === FAQ / UNCLEAR ===
        else:  # faq or unclear
            # Vector search
            embedding_service = EmbeddingService()
            query_embedding = await embedding_service.create_embedding(request.question)
            
            search_service = EnhancedSearchService()
            faqs_with_scores = await search_service.hybrid_search(
                session=session,
                query_embedding=query_embedding,
                query_text=request.question,
                language=language,
                limit=10
            )
            
            if not faqs_with_scores:
                # NO MATCH - persona fallback
                response_text = await gpt_service.generate_persona_response(
                    user_question=request.question,
                    intent="no_match",
                    language=language
                )
                
                if language == "kk":
                    response_text += "\n\n📞 Куратор қызметі: 10:00-20:00"
                else:
                    response_text += "\n\n📞 Служба куратора: 10:00-20:00"
                
                return AskResponse(
                    action="no_match",
                    question=request.question,
                    message=response_text,
                    confidence=0.0
                )
            
            best_score = faqs_with_scores[0][1]
            best_faq = faqs_with_scores[0][0]
            
            # 🔧 ИСПРАВЛЕНИЕ: Понижены пороги confidence для лучшего срабатывания
            
            # HIGH confidence (≥ 0.40) - ПРЯМОЙ ОТВЕТ С ВИДЕО
            if best_score >= 0.40:
                logger.info(f"✅ HIGH confidence: {best_score:.3f} - returning direct answer with video")
                
                return AskResponse(
                    action="direct_answer",
                    question=request.question,
                    answer_text=best_faq['answer_text'],
                    video_url=best_faq.get('video_url'),
                    faq_id=best_faq['id'],
                    confidence=best_score
                )
            
            # MEDIUM confidence (0.20-0.40) - GPT synthesizes BUT KEEP VIDEO!
            elif best_score >= 0.20:
                logger.info(f"🤔 MEDIUM confidence: {best_score:.3f} - GPT synthesis with video")
                
                answer = await gpt_service.generate_answer_from_faqs(
                    user_question=request.question,
                    matched_faqs=faqs_with_scores[:3],
                    language=language
                )
                
                return AskResponse(
                    action="direct_answer",
                    question=request.question,
                    answer_text=answer,
                    video_url=best_faq.get('video_url'),  # ✅ ВАЖНО: Оставляем видео!
                    faq_id=best_faq['id'],
                    confidence=best_score,
                    suggestions=[faq['question'] for faq, _ in faqs_with_scores[:3]]
                )
            
            # LOW confidence (0.10-0.20) - Clarification
            elif best_score >= 0.10:
                logger.info(f"📋 LOW confidence: {best_score:.3f} - asking for clarification")
                
                clarification = await gpt_service.generate_clarification_question(
                    user_question=request.question,
                    similar_faqs=faqs_with_scores[:3],
                    language=language
                )
                
                return AskResponse(
                    action="clarify",
                    question=request.question,
                    message=clarification,
                    confidence=best_score,
                    suggestions=[faq['question'] for faq, _ in faqs_with_scores[:3]]
                )
            
            # VERY LOW (<0.10) - Persona fallback BUT STILL SHOW BEST VIDEO IF EXISTS
            else:
                logger.info(f"❌ VERY LOW confidence: {best_score:.3f} - fallback with best match")
                
                response_text = await gpt_service.generate_persona_response(
                    user_question=request.question,
                    intent="unclear",
                    language=language,
                    context={"similar_faqs": [faq for faq, _ in faqs_with_scores[:3]]}
                )
                
                # ✅ НОВОЕ: Даже при no_match показываем лучшее видео, если есть
                return AskResponse(
                    action="no_match",
                    question=request.question,
                    message=response_text,
                    video_url=best_faq.get('video_url') if best_score > 0.05 else None,
                    faq_id=best_faq['id'] if best_score > 0.05 else None,
                    confidence=best_score
                )
    
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        
        # КРИТИЧНО: НЕ показывать техническую ошибку!
        if language == "kk":
            fallback = "Қазір техникалық ақау бар 🔧\n\nКуратор қызметіне жазыңыз, олар көмектеседі!\n📞 10:00-20:00"
        else:
            fallback = "Сейчас техническая неполадка 🔧\n\nНапишите куратору, он поможет!\n📞 10:00-20:00"
        
        return AskResponse(
            action="no_match",
            question=request.question,
            message=fallback,
            confidence=0.0
        )