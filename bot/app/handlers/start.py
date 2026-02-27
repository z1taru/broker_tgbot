# bot/app/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

router = Router()
logger = logging.getLogger(__name__)


class UserLanguage(StatesGroup):
    waiting_for_language = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """
    /start — тіл таңдау. Әдепкі қазақша.
    """
    user_name = message.from_user.first_name or "дос"

    # ✅ Әдепкі тіл — қазақша (кнопка басылмаса да)
    await state.update_data(language="kk")

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
        ]
    ])

    # ✅ Қазақша бірінші
    welcome_text = (
        f"Сәлем, {user_name}! 👋\n\n"
        f"Тілді таңдаңыз / Выберите язык:"
    )

    await message.answer(welcome_text, reply_markup=keyboard)
    await state.set_state(UserLanguage.waiting_for_language)


@router.callback_query(lambda c: c.data.startswith("lang:"))
async def process_language_selection(callback, state: FSMContext):
    language = callback.data.split(":")[1]

    await state.update_data(language=language)
    await state.clear()

    user_name = callback.from_user.first_name or "дос"

    if language == "kk":
        welcome_text = (
            f"Сәлем, {user_name}! 👋\n\n"
            f"Мен — инвестициялар бойынша AI-кураторың! 📊\n\n"
            f"Акциялар, облигациялар, шот ашу, дивидендтер және "
            f"инвестициялық стратегиялар туралы сұрақтарға жауап беремін.\n\n"
            f"💡 Мысалы:\n"
            f"• Екінші шот қалай ашамыз?\n"
            f"• Облигация қалай аламыз?\n"
            f"• Валюта айырбасы қалай жасалады?\n\n"
            f"Қандай сұрағың бар? 🤔\n\n"
            f"<i>Тілді өзгерту: /language</i>"
        )
    else:
        welcome_text = (
            f"Привет, {user_name}! 👋\n\n"
            f"Я — твой AI-куратор по инвестициям! 📊\n\n"
            f"Отвечаю на вопросы об акциях, облигациях, открытии счёта, "
            f"дивидендах и инвестиционных стратегиях.\n\n"
            f"💡 Например:\n"
            f"• Как открыть второй счет?\n"
            f"• Как купить облигацию?\n"
            f"• Обмен валюты\n\n"
            f"Какой у тебя вопрос? 🤔\n\n"
            f"<i>Сменить язык: /language</i>"
        )

    await callback.message.edit_text(welcome_text)
    await callback.answer()
    logger.info(f"User {callback.from_user.id} selected language: {language}")


@router.message(lambda message: message.text == "/language")
async def cmd_change_language(message: Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="lang:kk"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru")
        ]
    ])
    await message.answer(
        "Тілді таңдаңыз / Выберите язык:",
        reply_markup=keyboard
    )
    await state.set_state(UserLanguage.waiting_for_language)