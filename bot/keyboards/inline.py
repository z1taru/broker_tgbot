from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict


def get_categories_keyboard(categories: List[Dict]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с категориями вопросов
    
    Args:
        categories: список словарей с категориями
    """
    buttons = []
    
    # Маппинг категорий на человекочитаемые названия (казахский язык)
    category_names = {
        "tabys_pro": "📱 Tabys Pro",
        "freedom_broker": "🏦 Freedom Broker",
        "basics": "📚 Негіздер",
        "getting_started": "🚀 Қайдан бастау",
        "strategy": "📈 Стратегиялар",
        "analysis": "🔍 Талдау",
    }
    
    for category in categories:
        category_key = category if isinstance(category, str) else category.get("name", category)
        display_name = category_names.get(category_key, category_key.capitalize())
        
        buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"category:{category_key}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_questions_keyboard(faqs: List[Dict]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с вопросами из категории
    
    Args:
        faqs: список FAQ объектов
    """
    buttons = []
    
    for faq in faqs:
        # Ограничиваем длину текста кнопки
        question_text = faq["question"]
        if len(question_text) > 60:
            question_text = question_text[:57] + "..."
        
        buttons.append([
            InlineKeyboardButton(
                text=question_text,
                callback_data=f"faq:{faq['id']}"
            )
        ])
    
    # Кнопка "Назад" на казахском
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Санаттарға қайту",
            callback_data="back_to_categories"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой возврата к категориям (казахский)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Санаттарға қайту",
            callback_data="back_to_categories"
        )]
    ])