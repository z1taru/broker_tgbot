"""
Репозитории для работы с БД
"""
from app.repositories.base import BaseRepository
from app.repositories.faq_repository import FAQRepository

__all__ = [
    "BaseRepository",
    "FAQRepository",
]