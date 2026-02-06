from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from bot.app.core.database import Base


class FAQ(Base):
    __tablename__ = "faq"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    video_url = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    language = Column(String(10), default="kk", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Log(Base):
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String(100), nullable=False, index=True)
    question = Column(Text, nullable=True)
    matched_faq_id = Column(Integer, ForeignKey("faq.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)