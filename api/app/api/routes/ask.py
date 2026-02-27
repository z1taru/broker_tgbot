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
from app.ai.intent_router import IntentRouter

logger = get_logger(__name__)
router = APIRouter()

GREETING_WORDS = {
    'привет', 'сәлем', 'салем', 'hello', 'hi',
    'добрый', 'здравствуй', 'сәлеметсіз', 'қайырлы'
}

VAGUE_WORDS = {
    'дивиденды', 'карта', 'счет', 'счёт', 'акции', 'деньги',
    'помощь', 'помоги', 'вопрос', 'информация', 'как',
    'дивидендтер', 'карточка', 'шот', 'акциялар', 'ақша', 'көмек'
}

EXPLICIT_OFF_TOPIC = {
    'секс', 'порно', 'эротика', 'xxx', '18+', 'интим',
    'мультфильм', 'детское', 'балалар', 'бала', 'ребёнок', 'дети',
    'игрушка', 'сказка', 'мультик',
    'рецепт', 'готовить', 'еда', 'ресторан',
    'погода', 'температура', 'дождь', 'снег',
    'футбол', 'баскетбол', 'спорт', 'матч',
    'президент', 'выборы', 'партия', 'война',
    'лечение', 'болезнь', 'врач', 'таблетки',
}


def classify_intent_fast(text: str) -> str:
    lower = text.lower().strip()
    if any(w in lower for w in EXPLICIT_OFF_TOPIC):
        return 'off_topic'
    if any(w in lower for w in GREETING_WORDS) and len(lower) < 40:
        return 'greeting'
    return 'faq'


def is_vague_query(text: str) -> bool:
    lower = text.lower().strip()
    words = lower.split()
    return len(words) <= 2 and any(w in lower for w in VAGUE_WORDS)


def build_answer_text(faq: dict) -> str:
    answer = faq['answer_text']
    footer = faq.get('description_footer')
    if footer and footer.strip():
        answer = f"{answer}\n\n<i>{footer}</i>"
    return answer


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session)
):
    # ✅ Әдепкі тіл — қазақша. Орысша тек пайдаланушы таңдаса.
    language = "kk"

    try:
        if request.language == "auto":
            detector = LanguageDetector()
            language = detector.detect(request.question)
        elif request.language in ("kk", "ru"):
            language = request.language
        # Басқа мән болса — қазақша қалады

        logger.info(f"🔍 Question: '{request.question}' | Lang: {language}")

        intent = classify_intent_fast(request.question)
        logger.info(f"🎯 Intent: {intent}")

        gpt_service = GPTService()

        # === ТАҚЫРЫПТАН ТЫС ===
        if intent == 'off_topic':
            return AskResponse(
                action="no_match",
                question=request.question,
                message=gpt_service.get_off_topic_response(language),
                confidence=0.0
            )

        # === СӘЛЕМДЕСУ ===
        if intent == "greeting":
            response_text = await gpt_service.generate_persona_response(
                user_question=request.question,
                intent="greeting",
                language=language
            )
            if language == "kk":
                response_text += (
                    "\n\n💡 Мысалы:\n"
                    "• Шот қалай ашамыз?\n"
                    "• Облигация қалай аламыз?\n"
                    "• Валюта айырбасы"
                )
            else:
                response_text += (
                    "\n\n💡 Например:\n"
                    "• Как открыть счет?\n"
                    "• Как купить облигацию?\n"
                    "• Обмен валюты"
                )
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=response_text,
                confidence=1.0
            )

        # === ЖАЛПЫ СҰРАУ ===
        if is_vague_query(request.question):
            logger.info("🔎 Vague query")
            embedding_service = EmbeddingService()
            query_embedding = await embedding_service.create_embedding(request.question)
            search_service = EnhancedSearchService()
            faqs_with_scores = await search_service.hybrid_search(
                session=session,
                query_embedding=query_embedding,
                query_text=request.question,
                language=language,
                limit=4
            )
            clarification = await gpt_service.generate_clarification_question(
                user_question=request.question,
                similar_faqs=faqs_with_scores,
                language=language
            )
            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=0.5,
                suggestions=[faq['question'] for faq, _ in faqs_with_scores[:4]]
            )

        # === FAQ ІЗДЕУ ===
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

        # Нашар нәтиже — GPT тексеру
        if not faqs_with_scores or faqs_with_scores[0][1] < 0.30:
            intent_router = IntentRouter()
            gpt_intent = intent_router.detect_intent(request.question, language)
            logger.info(f"🤖 GPT intent: {gpt_intent}")
            if gpt_intent.get("intent") == "off_topic":
                return AskResponse(
                    action="no_match",
                    question=request.question,
                    message=gpt_service.get_off_topic_response(language),
                    confidence=0.0
                )

        if not faqs_with_scores:
            return AskResponse(
                action="no_match",
                question=request.question,
                message=await gpt_service.generate_no_match_response(
                    request.question, language
                ),
                confidence=0.0
            )

        best_score = faqs_with_scores[0][1]
        best_faq = faqs_with_scores[0][0]
        logger.info(f"📊 Best score: {best_score:.3f} | {best_faq['question'][:50]}")

        # ЖОҒАРЫ ≥ 0.40
        if best_score >= 0.40:
            return AskResponse(
                action="direct_answer",
                question=request.question,
                answer_text=build_answer_text(best_faq),
                video_url=best_faq.get('video_url'),
                faq_id=best_faq['id'],
                confidence=best_score
            )

        # ОРТАША 0.20–0.40
        elif best_score >= 0.20:
            close_matches = [
                (faq, score) for faq, score in faqs_with_scores[:5]
                if score >= best_score * 0.80
            ]
            if len(close_matches) >= 2:
                clarification = await gpt_service.generate_clarification_question(
                    request.question, close_matches, language
                )
                return AskResponse(
                    action="clarify",
                    question=request.question,
                    message=clarification,
                    confidence=best_score,
                    suggestions=[faq['question'] for faq, _ in close_matches[:4]]
                )
            else:
                answer = await gpt_service.generate_answer_from_faqs(
                    request.question, faqs_with_scores[:3], language
                )
                footer = best_faq.get('description_footer')
                if footer and footer.strip():
                    answer = f"{answer}\n\n<i>{footer}</i>"
                return AskResponse(
                    action="direct_answer",
                    question=request.question,
                    answer_text=answer,
                    video_url=best_faq.get('video_url'),
                    faq_id=best_faq['id'],
                    confidence=best_score
                )

        # ТӨМЕН 0.10–0.20
        elif best_score >= 0.10:
            clarification = await gpt_service.generate_clarification_question(
                request.question, faqs_with_scores[:3], language
            )
            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=best_score,
                suggestions=[faq['question'] for faq, _ in faqs_with_scores[:3]]
            )

        # ӨТЕ ТӨМЕН < 0.10
        else:
            return AskResponse(
                action="no_match",
                question=request.question,
                message=await gpt_service.generate_no_match_response(
                    request.question, language
                ),
                confidence=best_score
            )

    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        if language == "kk":
            fallback = "Қазір техникалық ақау бар 🔧\n\nКуратор қызметіне жазыңыз!\n📞 10:00-20:00"
        else:
            fallback = "Сейчас техническая неполадка 🔧\n\nНапишите куратору!\n📞 10:00-20:00"
        return AskResponse(
            action="no_match",
            question=request.question,
            message=fallback,
            confidence=0.0
        )