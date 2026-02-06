from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict


def get_categories_keyboard(categories: List[str]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с категориями вопросов
    """
    buttons = []
    
    category_names = {
        "tabys_pro": "📱 Tabys Pro",
        "freedom_broker": "🏦 Freedom Broker",
        "basics": "📚 Негіздер",
        "getting_started": "🚀 Қайдан бастау",
        "strategy": "📈 Стратегиялар",
        "analysis": "🔍 Талдау",
    }
    
    for category in categories:
        display_name = category_names.get(category, category.capitalize())
        
        buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"category:{category}"
            )
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_questions_keyboard(faqs: List[Dict]) -> InlineKeyboardMarkup:
    """
    Создаёт клавиатуру с вопросами из категории
    """
    buttons = []
    
    for faq in faqs:
        question_text = faq["question"]
        if len(question_text) > 60:
            question_text = question_text[:57] + "..."
        
        buttons.append([
            InlineKeyboardButton(
                text=question_text,
                callback_data=f"faq:{faq['id']}"
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text="◀️ Санаттарға қайту",
            callback_data="back_to_categories"
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_back_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с кнопкой возврата к категориям
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="◀️ Санаттарға қайту",
            callback_data="back_to_categories"
        )]
    ])