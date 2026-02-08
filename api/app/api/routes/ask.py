# api/app/api/routes/ask.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.ai.embeddings_enhanced import EmbeddingService
from app.ai.search_enhanced import EnhancedSearchService
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
    AI-powered question answering endpoint - УЛУЧШЕННАЯ ВЕРСИЯ
    """
    try:
        language = request.language
        if language == "auto":
            detector = LanguageDetector()
            language = detector.detect(request.question)
        
        logger.info(f"🔍 Processing: '{request.question}' | User: {request.user_id} | Lang: {language}")
        
        # 1. Создаём embedding
        embedding_service = EmbeddingService()
        query_embedding = await embedding_service.create_embedding(request.question)
        
        # 2. Ищем похожие FAQ
        search_service = EnhancedSearchService()
        rows = await search_service.find_similar_faqs(
            session=session,
            query_embedding=query_embedding,
            language=language,
            limit=10  # берём топ-10 для анализа
        )
        
        # 3. Преобразуем в список (faq_data, score)
        faqs_with_scores = []
        for row in rows:
            faq_data = {
                'id': row[0],
                'question': row[1],
                'answer_text': row[2],
                'video_url': row[3],
                'category': row[4],
                'language': row[5],
                'created_at': row[6]
            }
            similarity_score = float(row[7])
            faqs_with_scores.append((faq_data, similarity_score))
        
        logger.info(f"📊 Found {len(faqs_with_scores)} results. Top score: {faqs_with_scores[0][1]:.3f if faqs_with_scores else 0}")
        
        # 4. Умное принятие решения
        decision_engine = DecisionEngine()
        decision = decision_engine.make_decision(
            faqs_with_scores,
            user_question=request.question
        )
        
        action = decision["action"]
        score = decision["score"]
        
        # ============================================
        # ОБРАБОТКА РАЗНЫХ СЦЕНАРИЕВ
        # ============================================
        
        # ✅ ПРЯМОЙ ОТВЕТ (≥55%)
        if action == "direct_answer":
            faq_data = decision["faq"]
            
            # Проверяем, есть ли "medium match" флаг
            is_medium = decision.get("message") == "single_medium_match"
            confidence_text = ""
            
            if is_medium and language == "kk":
                confidence_text = "\n\n💡 Егер бұл дәл сол нәрсе болмаса - басқаша сұраңыз!"
            elif is_medium and language == "ru":
                confidence_text = "\n\n💡 Если это не совсем то - попробуйте переформулировать!"
            
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=faq_data['answer_text'] + confidence_text,
                video_url=faq_data.get('video_url'),
                faq_id=faq_data['id'],
                confidence=score
            )
        
        # 🤔 УТОЧНЕНИЕ (35-55% с несколькими вариантами)
        elif action == "clarify":
            # Формируем список вариантов
            options = decision["all_matches"][:3]
            
            if language == "kk":
                clarification = "Қайсысы сізге жақынырақ? 🤔\n\n"
                for i, (faq, sc) in enumerate(options, 1):
                    clarification += f"{i}️⃣ {faq['question']}\n"
                clarification += "\nСанын жазыңыз немесе сұрағыңызды нақтылаңыз 👆"
            else:
                clarification = "Какой из этих вопросов ближе к вашему? 🤔\n\n"
                for i, (faq, sc) in enumerate(options, 1):
                    clarification += f"{i}️⃣ {faq['question']}\n"
                clarification += "\nНапишите номер или уточните ваш вопрос 👆"
            
            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=score,
                suggestions=[faq['question'] for faq, _ in options]  # для UI
            )
        
        # 📋 ПОКАЗАТЬ ПОХОЖИЕ (20-35%)
        elif action == "show_similar":
            similar = decision["all_matches"][:5]
            
            if language == "kk":
                message = "Дәл сәйкестік таппадым, бірақ мына сұрақтар пайдалы болуы мүмкін:\n\n"
                for i, (faq, sc) in enumerate(similar, 1):
                    message += f"• {faq['question']}\n"
                message += "\nОсылардың біреуін таңдаңыз немесе басқаша сұраңыз 🔄"
            else:
                message = "Точного совпадения не нашёл, но может помогут эти вопросы:\n\n"
                for i, (faq, sc) in enumerate(similar, 1):
                    message += f"• {faq['question']}\n"
                message += "\nВыберите один из них или переформулируйте вопрос 🔄"
            
            return AskResponse(
                action="show_similar",
                question=request.question,
                message=message,
                confidence=score,
                suggestions=[faq['question'] for faq, _ in similar]
            )
        
        # ❌ НЕТ ОТВЕТА (<20%)
        else:  # no_match
            if language == "kk":
                fallback = (
                    "Кешіріңіз, жауап таба алмадым 😔\n\n"
                    "Сұрағыңызды кураторға жібердім.\n"
                    "10:00-20:00 арасында жауап береді! ⏰\n\n"
                    "Немесе басқаша сұраңыз 🔄"
                )
            else:
                fallback = (
                    "Извините, не нашёл ответа 😔\n\n"
                    "Отправил ваш вопрос куратору.\n"
                    "Ответит с 10:00 до 20:00! ⏰\n\n"
                    "Или попробуйте переформулировать 🔄"
                )
            
            # TODO: отправить куратору
            # await send_to_curator(request.user_id, request.question)
            
            return AskResponse(
                action="no_match",
                question=request.question,
                message=fallback,
                confidence=score
            )
    
    except Exception as e:
        logger.error(f"❌ Error processing question: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")