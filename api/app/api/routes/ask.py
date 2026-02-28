# api/app/api/routes/ask.py
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.schemas.ask import AskRequest, AskResponse
from app.core.logging_config import get_logger
from app.ai.gpt_service import GPTService
from app.ai.embeddings_enhanced import EmbeddingService
from app.ai.search_enhanced import EnhancedSearchService
from app.ai.llm_classifier import LLMClassifier, ClassificationResult

logger = get_logger(__name__)
router = APIRouter()

# Singleton instances — создаём один раз при старте, не на каждый запрос
_classifier = LLMClassifier(model="gpt-4o-mini")
_embedding_service = EmbeddingService()


def _build_answer_text(faq: dict) -> str:
    answer = faq["answer_text"]
    footer = faq.get("description_footer", "")
    if footer and footer.strip():
        answer = f"{answer}\n\n<i>{footer}</i>"
    return answer


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session),
):
    gpt = GPTService()
    search = EnhancedSearchService()

    # ── Шаг 1: classify + embedding ПАРАЛЛЕЛЬНО ───────────────────────────────
    # Экономим ~100ms — embedding запускается пока классификатор думает
    clf_task = asyncio.create_task(_classifier.classify(request.question))
    emb_task = asyncio.create_task(_embedding_service.create_embedding(request.question))

    clf: ClassificationResult
    query_embedding: list

    clf, query_embedding = await asyncio.gather(clf_task, emb_task)
    language = clf.language

    logger.info(
        f"[ASK] '{request.question[:60]}' | "
        f"lang={language} vague={clf.vague} intent={clf.intent} conf={clf.confidence:.2f}"
    )

    # ── Шаг 2: Off-topic — без поиска ─────────────────────────────────────────
    if clf.intent == "off_topic":
        return AskResponse(
            action="no_match",
            question=request.question,
            message=gpt.get_off_topic_response(language),
            confidence=0.0,
        )

    # ── Шаг 3: Greeting — без поиска ──────────────────────────────────────────
    if clf.intent == "greeting":
        text = await gpt.generate_persona_response(
            user_question=request.question,
            intent="greeting",
            language=language,
        )
        if language == "kk":
            text += (
                "\n\n💡 Мысалы:\n"
                "• Шот қалай ашамыз?\n"
                "• Облигация қалай аламыз?\n"
                "• Валюта айырбасы"
            )
        else:
            text += (
                "\n\n💡 Например:\n"
                "• Как открыть счет?\n"
                "• Как купить облигацию?\n"
                "• Обмен валюты"
            )
        return AskResponse(
            action="direct_answer",
            question=request.question,
            answer_text=text,
            confidence=1.0,
        )

    # ── Шаг 4: Поиск (embedding уже готов из gather) ──────────────────────────
    search_limit = 4 if clf.vague else 10

    faqs_with_scores = await search.hybrid_search(
        session=session,
        query_embedding=query_embedding,
        query_text=request.question,
        language=language,
        limit=search_limit,
    )

    # ── Шаг 5: Нет результатов ────────────────────────────────────────────────
    if not faqs_with_scores:
        return AskResponse(
            action="no_match",
            question=request.question,
            message=await gpt.generate_no_match_response(request.question, language),
            confidence=0.0,
        )

    best_faq, best_score = faqs_with_scores[0]
    logger.info(f"[ASK] best_score={best_score:.3f} | '{best_faq['question'][:50]}'")

    # ── Шаг 6: vague=true — ВСЕГДА уточняем ──────────────────────────────────
    if clf.vague:
        clarification = await gpt.generate_clarification_question(
            user_question=request.question,
            similar_faqs=faqs_with_scores[:4],
            language=language,
        )
        return AskResponse(
            action="clarify",
            question=request.question,
            message=clarification,
            confidence=best_score,
            suggestions=[faq["question"] for faq, _ in faqs_with_scores[:4]],
        )

    # ── Шаг 7: vague=false — Decision по score ────────────────────────────────

    # Высокий score ≥ 0.40 → прямой ответ
    if best_score >= 0.40:
        return AskResponse(
            action="direct_answer",
            question=request.question,
            answer_text=_build_answer_text(best_faq),
            video_url=best_faq.get("video_url"),
            faq_id=best_faq["id"],
            confidence=best_score,
        )

    # Средний score 0.20–0.40
    if best_score >= 0.20:
        close = [
            (faq, s) for faq, s in faqs_with_scores[:5]
            if s >= best_score * 0.80
        ]
        if len(close) >= 2:
            clarification = await gpt.generate_clarification_question(
                request.question, close, language
            )
            return AskResponse(
                action="clarify",
                question=request.question,
                message=clarification,
                confidence=best_score,
                suggestions=[faq["question"] for faq, _ in close[:4]],
            )
        # Один кандидат — генерируем ответ
        answer = await gpt.generate_answer_from_faqs(
            request.question, faqs_with_scores[:3], language
        )
        footer = best_faq.get("description_footer", "")
        if footer and footer.strip():
            answer = f"{answer}\n\n<i>{footer}</i>"
        return AskResponse(
            action="direct_answer",
            question=request.question,
            answer_text=answer,
            video_url=best_faq.get("video_url"),
            faq_id=best_faq["id"],
            confidence=best_score,
        )

    # Низкий score 0.10–0.20 → уточняем
    if best_score >= 0.10:
        clarification = await gpt.generate_clarification_question(
            request.question, faqs_with_scores[:3], language
        )
        return AskResponse(
            action="clarify",
            question=request.question,
            message=clarification,
            confidence=best_score,
            suggestions=[faq["question"] for faq, _ in faqs_with_scores[:3]],
        )

    # Очень низкий < 0.10 → no_match
    return AskResponse(
        action="no_match",
        question=request.question,
        message=await gpt.generate_no_match_response(request.question, language),
        confidence=best_score,
    )