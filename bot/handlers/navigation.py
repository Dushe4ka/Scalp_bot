from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import main_menu_kb
from bot.utils.helpers import safe_edit_message
from logger_config import setup_logger

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "main_menu")
async def back_to_main_menu(callback: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    user_id = callback.from_user.id
    
    # Очищаем состояние FSM если оно было установлено
    await state.clear()
    
    text = "👋 Главное меню\n\nВыберите действие:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=main_menu_kb(user_id).as_markup()
    )
    await callback.answer()

