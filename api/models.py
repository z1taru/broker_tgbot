from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base


class FAQ(Base):
    """Модель FAQ записей"""
    __tablename__ = "faq"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer_text = Column(Text, nullable=False)
    video_url = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, index=True)
    language = Column(String(10), default="ru")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Log(Base):
    """Модель логов действий пользователей"""
    __tablename__ = "logs"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String(100), nullable=False, index=True)
    question = Column(Text, nullable=True)
    matched_faq_id = Column(Integer, ForeignKey("faq.id", ondelete="SET NULL"), nullable=True)
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)