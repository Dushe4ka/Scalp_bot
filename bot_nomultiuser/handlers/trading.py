from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot_nomultiuser.keyboards.inline_kb import (
    trading_kb,
    algorithms_kb,
    stop_trading_kb,
    back_to_main_kb,
    result_position_info_kb,
)
from bot_nomultiuser.utils.helpers import safe_edit_message
from bot_nomultiuser.states.trading_states import TradingStates
from bot_nomultiuser.config import SERVER_URL
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
        reply_markup=trading_kb().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "algorithms")
async def algorithms_menu(callback: CallbackQuery):
    """Меню алгоритмов"""
    text = "🤖 Алгоритмы\n\nВыберите алгоритм:"

    await safe_edit_message(
        callback,
        text,
        reply_markup=algorithms_kb().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "nomulti_short_bu_ts_limit")
async def nomulti_short_bu_ts_limit_start(callback: CallbackQuery, state: FSMContext):
    """Запрос символа для Short BU TS limit (nemulti)."""
    text = "Введите символ (например BTCUSDT) для Short BU TS limit (nomulti):"
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup(),
    )
    await state.update_data(algorithm="nomulti_short")
    await state.set_state(TradingStates.waiting_for_symbol)
    await callback.answer()


@router.callback_query(F.data == "hedge_long_short_bu_ts")
async def hedge_long_short_bu_ts_start(callback: CallbackQuery, state: FSMContext):
    """Запрос символа для Hedge long + short."""
    text = "Введите символ (например BTCUSDT) для Hedge long + short:"
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup(),
    )
    await state.update_data(algorithm="hedge")
    await state.set_state(TradingStates.waiting_for_symbol)
    await callback.answer()


@router.message(TradingStates.waiting_for_symbol)
async def process_algorithm_symbol(message: Message, state: FSMContext):
    """Отправка символа на API в зависимости от выбранного алгоритма."""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    data = await state.get_data()
    algorithm = data.get("algorithm") or "nomulti_short"

    if algorithm == "hedge":
        url = f"{SERVER_URL}/hedge_long_short_bu_ts"
        algo_label = "Hedge long + short"
    else:
        url = f"{SERVER_URL}/nomulti_short_bu_ts_limit"
        algo_label = "Short BU TS limit (nomulti)"

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                url,
                data=symbol,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status == 200:
                    payload = await response.json()
                    tid = payload.get("task_id", "N/A")
                    text = (
                        f"✅ Запрос отправлён ({algo_label})\n\n"
                        f"Монета: {payload.get('symbol', symbol)}\n"
                        f"Task ID: {tid}\n"
                        f"Статус: {payload.get('status', 'N/A')}"
                    )
                    logger.info("Пользователь %s запустил %s для %s", user_id, algorithm, symbol)
                else:
                    err = await response.text()
                    text = f"❌ Ошибка API\n\nКод: {response.status}\n{err}"
                    logger.error("Ошибка %s: %s — %s", url, response.status, err)
    except aiohttp.ClientError as e:
        text = f"❌ Нет связи с сервером\n\n{str(e)}"
        logger.error("ClientError %s: %s", url, e)
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
        logger.error("Ошибка запуска алгоритма: %s", e)

    await message.answer(text, reply_markup=back_to_main_kb().as_markup())
    await state.clear()


@router.callback_query(F.data == "stop_trading")
async def stop_trading_menu(callback: CallbackQuery):
    """Меню остановки трейдинга"""
    text = "🛑 Остановка трейдинга\n\nВыберите способ:"

    await safe_edit_message(
        callback,
        text,
        reply_markup=stop_trading_kb().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "stop_by_symbol")
async def stop_by_symbol_start(callback: CallbackQuery, state: FSMContext):
    """Запрос названия монеты для остановки трейдинга"""
    text = "Введите название монеты для остановки трейдинга (например: BTCUSDT):"

    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup(),
    )
    await state.set_state(TradingStates.waiting_for_stop_symbol)
    await callback.answer()


@router.message(TradingStates.waiting_for_stop_symbol)
async def process_stop_by_symbol(message: Message, state: FSMContext):
    """Обработка ввода монеты для остановки трейдинга"""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{SERVER_URL}/stop_trading_by_symbol",
                json={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = (
                        f"✅ Трейдинг остановлен!\n\n"
                        f"Монета: {symbol}\n"
                        f"Сообщение: {data.get('message', 'Алгоритм остановлен')}"
                    )
                    logger.info("Пользователь %s остановил трейдинг для %s", user_id, symbol)
                else:
                    err = await response.text()
                    text = f"❌ Ошибка остановки\n\nКод: {response.status}\n{err}"
                    logger.error("Ошибка stop: %s — %s", response.status, err)
    except aiohttp.ClientError as e:
        text = f"❌ Нет связи с сервером\n\n{str(e)}"
        logger.error("ClientError stop: %s", e)
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
        logger.error("Ошибка остановки: %s", e)

    await message.answer(text, reply_markup=back_to_main_kb().as_markup())
    await state.clear()


@router.callback_query(F.data == "stop_trading_all")
async def stop_trading_all_start(callback: CallbackQuery):
    """Остановка всех алгоритмов трейдинга"""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{SERVER_URL}/stop_trading_all",
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Все алгоритмы остановлены!\n\n{data.get('message', '')}"
                    logger.info("Все алгоритмы остановлены")
                else:
                    err = await response.text()
                    text = f"❌ Ошибка\n\nКод: {response.status}\n{err}"
                    logger.error("stop_all: %s", response.status)
    except aiohttp.ClientError as e:
        text = f"❌ Нет связи с сервером\n\n{str(e)}"
        logger.error("ClientError stop_all: %s", e)
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
        logger.error("Ошибка stop_all: %s", e)

    await callback.message.answer(text, reply_markup=back_to_main_kb().as_markup())
    await callback.answer()


@router.callback_query(F.data == "result_position_info")
async def result_position_info_start(callback: CallbackQuery):
    """Меню получения информации о позиции"""
    text = "💰 Информация о позиции\n\nВыберите способ:"

    await safe_edit_message(
        callback,
        text,
        reply_markup=result_position_info_kb().as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data == "result_position_info_by_symbol")
async def result_position_info_by_symbol_start(callback: CallbackQuery, state: FSMContext):
    """Ввод монеты для информации о позиции"""
    text = "Введите символ (например BTCUSDT):"

    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup(),
    )
    await state.set_state(TradingStates.waiting_for_info_symbol)
    await callback.answer()


@router.message(TradingStates.waiting_for_info_symbol)
async def process_result_position_info_by_symbol(message: Message, state: FSMContext):
    """Запрос информации о позиции по символу"""
    symbol = message.text.strip().upper()
    user_id = message.from_user.id

    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{SERVER_URL}/result_position_info_by_symbol",
                json={"symbol": symbol},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = f"✅ Информация:\n\n{data.get('result', '—')}"
                    logger.info("Пользователь %s: position info %s", user_id, symbol)
                else:
                    err = await response.text()
                    text = f"❌ Ошибка\n\nКод: {response.status}\n{err}"
    except aiohttp.ClientError as e:
        text = f"❌ Нет связи с сервером\n\n{str(e)}"
        logger.error("ClientError position info: %s", e)
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
        logger.error("Ошибка position info: %s", e)

    await message.answer(text, reply_markup=back_to_main_kb().as_markup())
    await state.clear()
