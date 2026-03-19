from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.config import SERVER_URL
from bot._old.keyboards.inline_kb import account_kb, account_balance_kb
from bot.utils.helpers import safe_edit_message
from logger_config import setup_logger
import aiohttp

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "account")
async def account_menu(callback: CallbackQuery):
    """Меню аккаунта"""
    text = "👤 Аккаунт\n\nВыберите действие:"
    await safe_edit_message(
        callback,
        text,
        reply_markup=account_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "account_balance")
async def account_balance(callback: CallbackQuery):
    """Баланс аккаунта"""
    text = "💰 Баланс аккаунта\n\nВыберите действие:"
    await safe_edit_message(
        callback,
        text,
        reply_markup=account_balance_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "account_balance_futures")
async def account_balance_futures(callback: CallbackQuery):
    """Баланс futures аккаунта"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{SERVER_URL}/futures_balance", timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    data = await response.json()
                    balance = data.get("balance", 0)
                    text = f"💰 Баланс futures аккаунта: {balance} USDT"
                else:
                    text = f"❌ Ошибка получения баланса futures аккаунта: {response.status}"
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка получения баланса futures аккаунта: {str(e)}"
        logger.error(f"Ошибка получения баланса futures аккаунта: {e}")
    except Exception as e:
        text = f"❌ Ошибка получения баланса futures аккаунта: {str(e)}"
        logger.error(f"Ошибка получения баланса futures аккаунта: {e}")

    await safe_edit_message(
        callback,
        text,
        reply_markup=account_balance_kb().as_markup()
    )
    await callback.answer()
