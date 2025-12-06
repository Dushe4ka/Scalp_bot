from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.keyboards.inline_kb import trading_kb, algorithms_kb, stop_trading_kb, back_to_main_kb, result_position_info_kb
from bot.utils.helpers import safe_edit_message
from bot.states.trading_states import TradingStates
from bot.config import SERVER_URL
from logger_config import setup_logger
import aiohttp

router = Router()
logger = setup_logger(__name__)

@router.callback_query(F.data == "trading")
async def trading_menu(callback: CallbackQuery):
    """Меню трейдинга"""
    text = "📈 Трейдинг\n\nВыберите действие:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=trading_kb().as_markup()
    )
    await callback.answer()

# ============================================
# Ветка кнопок для алгоритмов
# ============================================
@router.callback_query(F.data == "algorithms")
async def algorithms_menu(callback: CallbackQuery):
    """Меню алгоритмов"""
    text = "🤖 Алгоритмы\n\nВыберите алгоритм:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=algorithms_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "short_3_limit")
async def short_3_limit_start(callback: CallbackQuery, state: FSMContext):
    """Запрос названия монеты для Short 3 limit"""
    text = "Введите название монеты (например: BTCUSDT):"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.set_state(TradingStates.waiting_for_symbol)
    await callback.answer()

@router.message(TradingStates.waiting_for_symbol)
async def process_short_3_limit(message: Message, state: FSMContext):
    """Обработка ввода монеты для Short 3 limit"""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SERVER_URL}/short_3_limit",
                json={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Запрос успешно отправлен!\n\n" \
                           f"Монета: {data.get('symbol', symbol)}\n" \
                           f"Task ID: {data.get('task_id', 'N/A')}\n" \
                           f"Статус: {data.get('status', 'N/A')}"
                    logger.info(f"Пользователь {user_id} запустил short_3_limit для {symbol}")
                else:
                    error_text = await response.text()
                    text = f"❌ Ошибка отправки запроса\n\nКод: {response.status}\nОшибка: {error_text}"
                    logger.error(f"Ошибка запуска short_3_limit: {response.status} - {error_text}")
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка подключения к серверу\n\n{str(e)}"
        logger.error(f"Ошибка подключения при запуске short_3_limit: {e}")
    except Exception as e:
        text = f"❌ Произошла ошибка\n\n{str(e)}"
        logger.error(f"Неожиданная ошибка при запуске short_3_limit: {e}")
    
    await message.answer(
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.clear()

# ============================================
# Ветка кнопок для остановки трейдинга
# ============================================
@router.callback_query(F.data == "stop_trading")
async def stop_trading_menu(callback: CallbackQuery):
    """Меню остановки трейдинга"""
    text = "🛑 Остановка трейдинга\n\nВыберите способ:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=stop_trading_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "stop_by_symbol")
async def stop_by_symbol_start(callback: CallbackQuery, state: FSMContext):
    """Запрос названия монеты для остановки трейдинга"""
    text = "Введите название монеты для остановки трейдинга (например: BTCUSDT):"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.set_state(TradingStates.waiting_for_stop_symbol)
    await callback.answer()

@router.message(TradingStates.waiting_for_stop_symbol)
async def process_stop_by_symbol(message: Message, state: FSMContext):
    """Обработка ввода монеты для остановки трейдинга"""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SERVER_URL}/stop_trading_by_symbol",
                json={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Трейдинг остановлен!\n\n" \
                           f"Монета: {symbol}\n" \
                           f"Сообщение: {data.get('message', 'Алгоритм остановлен')}"
                    logger.info(f"Пользователь {user_id} остановил трейдинг для {symbol}")
                else:
                    error_text = await response.text()
                    text = f"❌ Ошибка остановки трейдинга\n\nКод: {response.status}\nОшибка: {error_text}"
                    logger.error(f"Ошибка остановки трейдинга: {response.status} - {error_text}")
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка подключения к серверу\n\n{str(e)}"
        logger.error(f"Ошибка подключения при остановке трейдинга: {e}")
    except Exception as e:
        text = f"❌ Произошла ошибка\n\n{str(e)}"
        logger.error(f"Неожиданная ошибка при остановке трейдинга: {e}")
    
    await message.answer(
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.clear()

@router.callback_query(F.data == "stop_trading_all")
async def stop_trading_all_start(callback: CallbackQuery):
    """Остановка всех алгоритмов трейдинга"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SERVER_URL}/stop_trading_all",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Все алгоритмы остановлены!\n\n{data.get('message', 'Все алгоритмы остановлены')}"
                    logger.info(f"Все алгоритмы остановлены")
                else:
                    error_text = await response.text()
                    text = f"❌ Ошибка остановки всех алгоритмов\n\nКод: {response.status}\nОшибка: {error_text}"
                    logger.error(f"Ошибка остановки всех алгоритмов: {response.status} - {error_text}")
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка подключения к серверу\n\n{str(e)}"
        logger.error(f"Ошибка подключения при остановке всех алгоритмов: {e}")
    except Exception as e:
        text = f"❌ Произошла ошибка\n\n{str(e)}"
        logger.error(f"Неожиданная ошибка при остановке всех алгоритмов: {e}")
    
    await callback.message.answer(
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await callback.answer()

 # ============================================
 # Ветка кнопок для получения информации о позиции
 # ============================================
@router.callback_query(F.data == "result_position_info")
async def result_position_info_start(callback: CallbackQuery):
    """Меню получения информации о позиции"""
    text = "💰 Информация о позиции\n\nВыберите способ:"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=result_position_info_kb().as_markup()
    )
    await callback.answer()

@router.callback_query(F.data == "result_position_info_by_symbol")
async def result_position_info_by_symbol_start(callback: CallbackQuery, state: FSMContext):
    """Обработка ввода монеты для получения информации о позиции"""
    text = "Введите название монеты для получения информации о позиции (например: BTCUSDT):"
    
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.set_state(TradingStates.waiting_for_info_symbol)
    await callback.answer()

@router.message(TradingStates.waiting_for_info_symbol)
async def process_result_position_info_by_symbol(message: Message, state: FSMContext):
    """Обработка ввода монеты для получения информации о позиции"""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{SERVER_URL}/result_position_info_by_symbol",
                json={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Информация о позиции получена!\n\n" \
                           f"Сообщение: {data.get('result', 'Информация о позиции не найдена')}"
                    logger.info(f"Пользователь {user_id} получил информацию о позиции для {symbol}")
                else:
                    error_text = await response.text()
                    text = f"❌ Ошибка получения информации о позиции\n\nКод: {response.status}\nОшибка: {error_text}"
                    logger.error(f"Ошибка получения информации о позиции: {response.status} - {error_text}")
    except aiohttp.ClientError as e:
        text = f"❌ Ошибка подключения к серверу\n\n{str(e)}"
        logger.error(f"Ошибка подключения при получении информации о позиции: {e}")
    except Exception as e:
        text = f"❌ Произошла ошибка\n\n{str(e)}"
        logger.error(f"Неожиданная ошибка при получении информации о позиции: {e}")
    
    await message.answer(
        text,
        reply_markup=back_to_main_kb().as_markup()
    )
    await state.clear()