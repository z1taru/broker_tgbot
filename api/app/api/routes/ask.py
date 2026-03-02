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
from app.ai.llm_classifier import LLMClassifier

logger = get_logger(__name__)
router = APIRouter()

_classifier = LLMClassifier(model="gpt-4o-mini")
_embedding_service = EmbeddingService()


def _build_answer_text(faq: dict) -> str:
    answer = faq["answer_text"]
    footer = faq.get("description_footer", "")
    if footer and str(footer).strip():
        answer = f"{answer}\n\n<i>{footer}</i>"
    return answer


def _pick_clarify_options(faqs_with_scores: list, max_count: int = 4) -> tuple[list, list]:
    """
    Выбрать top-4 варианта с дедупликацией по тексту.
    Возвращает (titles: list[str], faq_ids: list[int]).
    """
    seen: set[str] = set()
    titles: list[str] = []
    ids: list[int] = []

    for faq, score in faqs_with_scores:
        norm = faq["question"].lower().strip()
        if norm in seen:
            continue
        seen.add(norm)
        titles.append(faq["question"])
        ids.append(faq["id"])
        if len(titles) >= max_count:
            break

    return titles, ids


@router.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    session: AsyncSession = Depends(get_session),
):
    gpt = GPTService()
    search = EnhancedSearchService()

    # Classify + embedding параллельно
    clf, query_embedding = await asyncio.gather(
        _classifier.classify(request.question),
        _embedding_service.create_embedding(request.question),
    )
    language = clf.language

    logger.info(
        f"[ASK] '{request.question[:60]}' | "
        f"lang={language} vague={clf.vague} intent={clf.intent} conf={clf.confidence:.2f}"
    )

    # Off-topic
    if clf.intent == "off_topic":
        return AskResponse(
            action="no_match",
            question=request.question,
            detected_language=language,
            message=gpt.get_off_topic_response(language),
            confidence=0.0,
        )

    # Greeting
    if clf.intent == "greeting":
        text = await gpt.generate_persona_response(
            user_question=request.question,
            intent="greeting",
            language=language,
        )
        if language == "kk":
            text += "\n\n💡 Мысалы:\n• Шот қалай ашамыз?\n• Облигация қалай аламыз?\n• Валюта айырбасы"
        else:
            text += "\n\n💡 Например:\n• Как открыть счет?\n• Как купить облигацию?\n• Обмен валюты"
        return AskResponse(
            action="direct_answer",
            question=request.question,
            detected_language=language,
            answer_text=text,
            confidence=1.0,
        )

    # Поиск (берём 8 с запасом для дедупа)
    faqs_with_scores = await search.hybrid_search(
        session=session,
        query_embedding=query_embedding,
        query_text=request.question,
        language=language,
        limit=8,
    )

    if not faqs_with_scores:
        return AskResponse(
            action="no_match",
            question=request.question,
            detected_language=language,
            message=await gpt.generate_no_match_response(request.question, language),
            confidence=0.0,
        )

    best_faq, best_score = faqs_with_scores[0]
    logger.info(f"[ASK] best_score={best_score:.3f} | '{best_faq['question'][:50]}'")

    # vague=true → всегда clarify с 4 вариантами
    if clf.vague:
        titles, faq_ids = _pick_clarify_options(faqs_with_scores, max_count=4)
        clarification = await gpt.generate_clarification_question(
            user_question=request.question,
            similar_faqs=faqs_with_scores[:4],
            language=language,
        )
        return AskResponse(
            action="clarify",
            question=request.question,
            detected_language=language,
            message=clarification,
            confidence=best_score,
            suggestions=titles,
            suggestion_ids=faq_ids,
        )

    # score >= 0.40 → прямой ответ
    if best_score >= 0.40:
        return AskResponse(
            action="direct_answer",
            question=request.question,
            detected_language=language,
            answer_text=_build_answer_text(best_faq),
            video_url=best_faq.get("video_url"),
            faq_id=best_faq["id"],
            confidence=best_score,
        )

    # score 0.20–0.40 → несколько близких?
    if best_score >= 0.20:
        close = [(f, s) for f, s in faqs_with_scores[:6] if s >= best_score * 0.80]
        if len(close) >= 2:
            titles, faq_ids = _pick_clarify_options(close, max_count=4)
            clarification = await gpt.generate_clarification_question(
                request.question, close[:4], language
            )
            return AskResponse(
                action="clarify",
                question=request.question,
                detected_language=language,
                message=clarification,
                confidence=best_score,
                suggestions=titles,
                suggestion_ids=faq_ids,
            )
        answer = await gpt.generate_answer_from_faqs(request.question, faqs_with_scores[:3], language)
        footer = best_faq.get("description_footer", "")
        if footer and str(footer).strip():
            answer = f"{answer}\n\n<i>{footer}</i>"
        return AskResponse(
            action="direct_answer",
            question=request.question,
            detected_language=language,
            answer_text=answer,
            video_url=best_faq.get("video_url"),
            faq_id=best_faq["id"],
            confidence=best_score,
        )

    # score 0.10–0.20
    if best_score >= 0.10:
        titles, faq_ids = _pick_clarify_options(faqs_with_scores[:4], max_count=4)
        clarification = await gpt.generate_clarification_question(
            request.question, faqs_with_scores[:4], language
        )
        return AskResponse(
            action="clarify",
            question=request.question,
            detected_language=language,
            message=clarification,
            confidence=best_score,
            suggestions=titles,
            suggestion_ids=faq_ids,
        )

    # < 0.10 → no_match
    return AskResponse(
        action="no_match",
        question=request.question,
        detected_language=language,
        message=await gpt.generate_no_match_response(request.question, language),
        confidence=best_score,
    )