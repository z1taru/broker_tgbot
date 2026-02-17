# api/app/api/routes/ask.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.core.logging_config import get_logger

from app.ai.gpt_service import GPTService
from app.ai.embeddings_enhanced import EmbeddingService
from app.ai.search_enhanced import EnhancedSearchService
from app.ai.language_detector import LanguageDetector

logger = get_logger(__name__)
router = APIRouter()

# Быстрая классификация без LLM
GREETING_WORDS = {
    'привет', 'сәлем', 'салем', 'hello', 'hi',
    'добрый', 'здравствуй', 'сәлеметсіз', 'қайырлы'
}

def classify_intent_fast(text: str) -> str:
    lower = text.lower().strip()
    if any(w in lower for w in GREETING_WORDS) and len(lower) < 40:
        return 'greeting'
    return 'faq'


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session)
):
    try:
        # 1. Language detection
        language = request.language
        if language == "auto":
            detector = LanguageDetector()
            language = detector.detect(request.question)

        logger.info(f"🔍 Question: '{request.question}' | Lang: {language}")

        # 2. Fast intent — без LLM
        intent = classify_intent_fast(request.question)
        logger.info(f"🎯 Intent: {intent}")

        gpt_service = GPTService()

        # === GREETING ===
        if intent == "greeting":
            response_text = await gpt_service.generate_persona_response(
                user_question=request.question,
                intent="greeting",
                language=language
            )

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

        # === FAQ — всё остальное идёт в векторный поиск ===
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
            if language == "kk":
                response_text = "Кешіріңіз, бұл тақырып бойынша ақпарат таба алмадым 🤔\n\n📞 Куратор қызметі: 10:00-20:00"
            else:
                response_text = "Извините, не нашёл информацию по этому вопросу 🤔\n\n📞 Служба куратора: 10:00-20:00"

            return AskResponse(
                action="no_match",
                question=request.question,
                message=response_text,
                confidence=0.0
            )

        best_score = faqs_with_scores[0][1]
        best_faq = faqs_with_scores[0][0]

        logger.info(f"📊 Best score: {best_score:.3f} | FAQ: {best_faq['question'][:50]}")

        # HIGH confidence (>= 0.40) — прямой ответ с видео
        if best_score >= 0.40:
            logger.info(f"✅ HIGH confidence: {best_score:.3f}")
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=best_faq['answer_text'],
                video_url=best_faq.get('video_url'),
                faq_id=best_faq['id'],
                confidence=best_score
            )

        # MEDIUM confidence (0.20-0.40) — GPT синтез
        elif best_score >= 0.20:
            logger.info(f"🤔 MEDIUM confidence: {best_score:.3f}")
            answer = await gpt_service.generate_answer_from_faqs(
                user_question=request.question,
                matched_faqs=faqs_with_scores[:3],
                language=language
            )
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=answer,
                video_url=best_faq.get('video_url'),
                faq_id=best_faq['id'],
                confidence=best_score,
                suggestions=[faq['question'] for faq, _ in faqs_with_scores[:3]]
            )

        # LOW confidence (0.10-0.20) — уточняющий вопрос без LLM
        elif best_score >= 0.10:
            logger.info(f"📋 LOW confidence: {best_score:.3f}")
            options = '\n'.join(
                f"{i}. {faq['question']}"
                for i, (faq, _) in enumerate(faqs_with_scores[:3], 1)
            )
            if language == "kk":
                clarification = f"Қайсысы сізге жақынырақ? 🤔\n\n{options}\n\n💬 Санын жазыңыз немесе нақтылаңыз"
            else:
                clarification = f"Какой из этих вопросов ближе к вашему? 🤔\n\n{options}\n\n💬 Напишите номер или уточните вопрос"

            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=best_score,
                suggestions=[faq['question'] for faq, _ in faqs_with_scores[:3]]
            )

        # VERY LOW (< 0.10) — no match
        else:
            logger.info(f"❌ VERY LOW confidence: {best_score:.3f}")
            if language == "kk":
                response_text = "Кешіріңіз, жауап таба алмадым 🤔\n\nСұрағыңызды басқаша қойып көріңіз немесе куратор қызметіне жазыңыз.\n📞 10:00-20:00"
            else:
                response_text = "Извините, не нашёл ответа на ваш вопрос 🤔\n\nПопробуйте переформулировать или напишите куратору.\n📞 10:00-20:00"

            return AskResponse(
                action="no_match",
                question=request.question,
                message=response_text,
                confidence=best_score
            )

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)

        if language == "kk":
            fallback = "Қазір техникалық ақау бар 🔧\n\nКуратор қызметіне жазыңыз!\n📞 10:00-20:00"
        else:
            fallback = "Сейчас техническая неполадка 🔧\n\nНапишите куратору, он поможет!\n📞 10:00-20:00"

        return AskResponse(
            action="no_match",
            question=request.question,
            message=fallback,
            confidence=0.0
        )