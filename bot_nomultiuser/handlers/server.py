from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot_nomultiuser.keyboards.inline_kb import server_kb, main_menu_kb
from bot_nomultiuser.utils.helpers import safe_edit_message
from bot_nomultiuser.config import SERVER_URL
from logger_config import setup_logger
import aiohttp

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "server")
async def server_menu(callback: CallbackQuery):
    """Меню сервера"""
    text = "🖥 Сервер\n\nВыберите действие:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=server_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "check_health")
async def check_health(callback: CallbackQuery):
    """Проверка работоспособности сервера"""
    user_id = callback.from_user.id
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SERVER_URL}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    status = data.get("status", "unknown")
                    text = f"✅ Сервер работает!\n\nСтатус: {status}\nСервис: {data.get('service', 'N/A')}"
                else:
                    text = f"❌ Сервер недоступен\n\nКод ответа: {response.status}"
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка подключения к серверу\n\n{str(e)}"
        logger.error(f"Ошибка проверки здоровья сервера: {e}")
    except Exception as e:
        text = f"❌ Произошла ошибка\n\n{str(e)}"
        logger.error(f"Неожиданная ошибка при проверке здоровья: {e}")
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=server_kb().as_markup()
    )
    await callback.answer()

