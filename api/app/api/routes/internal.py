import os
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from app.core.database import get_session
from app.ai.embeddings_enhanced import EmbeddingService
from app.core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

INTERNAL_SECRET = os.environ['INTERNAL_WEBHOOK_SECRET']

class RebuildRequest(BaseModel):
    faq_content_id: int

def verify_secret(x_internal_secret: str = Header(...)):
    if x_internal_secret != INTERNAL_SECRET:
        raise HTTPException(status_code=403, detail='Forbidden')

@router.post('/internal/embeddings/rebuild')
async def rebuild_embedding(
    body: RebuildRequest,
    session: AsyncSession = Depends(get_session),
    _: None = Depends(verify_secret)
):
    row = await session.execute(
        text('SELECT question, answer_text FROM faq_content WHERE id = :id'),
        {'id': body.faq_content_id}
    )
    record = row.fetchone()
    if not record:
        raise HTTPException(status_code=404, detail='faq_content not found')

    emb_service = EmbeddingService()
    combined = f"{record[0]} {record[1]}"
    embedding = await emb_service.create_embedding(combined)
    emb_str = '[' + ','.join(map(str, embedding)) + ']'

    await session.execute(
        text('UPDATE faq_content SET question_embedding = CAST(:emb AS vector) WHERE id = :id'),
        {'emb': emb_str, 'id': body.faq_content_id}
    )
    await session.commit()
    logger.info(f'Rebuilt embedding for faq_content_id={body.faq_content_id}')
    return {'status': 'ok', 'faq_content_id': body.faq_content_id}
