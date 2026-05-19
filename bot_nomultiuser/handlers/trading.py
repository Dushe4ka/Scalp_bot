from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot_nomultiuser.keyboards.inline_kb import (
    trading_kb,
    algorithms_kb,
    stop_trading_kb,
    back_to_main_kb,
    result_position_info_kb,
    custom_algo_config_kb,
    custom_algo_saved_kb,
    custom_algo_confirm_kb,
    custom_step_back_kb,
    custom_launch_amount_back_kb,
)
from bot_nomultiuser.utils.helpers import safe_edit_message
from bot_nomultiuser.states.trading_states import TradingStates
from bot_nomultiuser.config import SERVER_URL
from logger_config import setup_logger
from custom_algo_repository import custom_algo_db, normalize_custom_config, CustomAlgoValidationError
import aiohttp

router = Router()
logger = setup_logger(__name__)

DEFAULT_CUSTOM_CONFIG = {
    "direction": "long",
    "use_trailing_stop": False,
    "trailing_activate_pct": None,
    "trailing_step_pct": None,
    "use_stop_loss": False,
    "stop_loss_pct": None,
    "use_breakeven": False,
    "breakeven_pct": None,
    "order_amount_usdt": 10.0,
}


def _format_custom_config(config: dict) -> str:
    side_text = "Лонг" if config.get("direction") == "long" else "Шорт"

    def fmt_bool(value: bool) -> str:
        return "✅ Включено" if value else "❌ Выключено"

    def fmt_pct(value: float | None) -> str:
        return f"{value:g}%" if isinstance(value, (float, int)) else "—"

    amount = config.get("order_amount_usdt")
    amount_text = f"{amount:g} USDT" if isinstance(amount, (float, int)) else "Не задана (спросим при запуске)"

    lines = [
        "⚙️ Custom Algo",
        "",
        f"Сторона: {side_text}",
        f"Трейлинг стоп: {fmt_bool(config.get('use_trailing_stop', False))}",
        f"  • Активация: {fmt_pct(config.get('trailing_activate_pct'))}",
        f"  • Шаг трейлинга: {fmt_pct(config.get('trailing_step_pct'))}",
        f"Стоп-лосс: {fmt_bool(config.get('use_stop_loss', False))}",
        f"  • SL %: {fmt_pct(config.get('stop_loss_pct'))}",
        f"БУ: {fmt_bool(config.get('use_breakeven', False))}",
        f"  • BU %: {fmt_pct(config.get('breakeven_pct'))}",
        f"Сумма сделки: {amount_text}",
    ]
    return "\n".join(lines)


def _build_custom_steps(config: dict) -> list[tuple[str, str]]:
    steps: list[tuple[str, str]] = []
    if config.get("use_trailing_stop"):
        steps.append(("trailing_step_pct", "Введите шаг трейлинга в % (например 1):"))
        steps.append(("trailing_activate_pct", "Введите % активации трейлинга (например 2):"))
    if config.get("use_stop_loss"):
        steps.append(("stop_loss_pct", "Введите % стоп-лосса (например 3):"))
    if config.get("use_breakeven"):
        steps.append(("breakeven_pct", "Введите % для БУ (например 3):"))
    steps.append(("order_amount_usdt", "Введите сумму сделки в USDT (0 = не фиксировать):"))
    return steps


def _step_to_state(step_key: str) -> TradingStates:
    mapping = {
        "trailing_step_pct": TradingStates.waiting_for_custom_trailing_step,
        "trailing_activate_pct": TradingStates.waiting_for_custom_trailing_activate,
        "stop_loss_pct": TradingStates.waiting_for_custom_stop_loss,
        "breakeven_pct": TradingStates.waiting_for_custom_breakeven,
        "order_amount_usdt": TradingStates.waiting_for_custom_order_amount,
    }
    return mapping[step_key]


async def _show_custom_builder(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    config = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    text = "Настройка Custom алгоритма\n\nВыберите параметры:"
    await safe_edit_message(
        callback,
        text,
        reply_markup=custom_algo_config_kb(config).as_markup(),
    )


async def _start_custom_step(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    config = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    steps = _build_custom_steps(config)
    if not steps:
        await callback.answer("Нет шагов для заполнения")
        return
    await state.update_data(custom_steps=steps, custom_step_index=0)
    first_step_key, first_prompt = steps[0]
    await safe_edit_message(callback, f"📝 {first_prompt}", reply_markup=custom_step_back_kb().as_markup())
    await state.set_state(_step_to_state(first_step_key))


async def _handle_custom_step_input(message: Message, state: FSMContext, field_name: str):
    raw = (message.text or "").strip().replace(",", ".")
    data = await state.get_data()
    draft = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    steps = data.get("custom_steps", [])
    idx = int(data.get("custom_step_index", 0))

    try:
        value = float(raw)
    except ValueError:
        await message.answer("Введите число, например: 1.5")
        return

    if field_name == "order_amount_usdt" and value == 0:
        draft[field_name] = None
    else:
        if value <= 0:
            await message.answer("Значение должно быть больше 0")
            return
        draft[field_name] = value

    await state.update_data(custom_draft=draft)

    if idx + 1 >= len(steps):
        try:
            normalized = normalize_custom_config(draft)
        except CustomAlgoValidationError as exc:
            await message.answer(f"❌ Ошибка конфигурации: {exc}")
            await state.clear()
            return
        await state.update_data(custom_pending_config=normalized)
        await message.answer(
            f"{_format_custom_config(normalized)}\n\nПроверьте настройки и подтвердите:",
            reply_markup=custom_algo_confirm_kb().as_markup(),
        )
        return

    next_idx = idx + 1
    next_step_key, next_prompt = steps[next_idx]
    await state.update_data(custom_step_index=next_idx, custom_draft=draft, custom_steps=steps)
    await message.answer(next_prompt, reply_markup=custom_step_back_kb().as_markup())
    await state.set_state(_step_to_state(next_step_key))


async def _launch_custom_algo(message: Message, state: FSMContext, symbol: str, order_amount_override: float | None):
    tg_id = message.from_user.id
    payload = {
        "symbol": symbol,
        "tg_id": tg_id,
        "order_amount_override": order_amount_override,
    }
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{SERVER_URL}/nomulti_custom_algo",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    text = (
                        "✅ Запрос отправлён (Custom Algo)\n\n"
                        f"Монета: {data.get('symbol', symbol)}\n"
                        f"Task ID: {data.get('task_id', 'N/A')}\n"
                        f"Статус: {data.get('status', 'N/A')}"
                    )
                else:
                    err = await response.text()
                    text = f"❌ Ошибка API\n\nКод: {response.status}\n{err}"
    except aiohttp.ClientError as e:
        text = f"❌ Нет связи с сервером\n\n{str(e)}"
    except Exception as e:
        text = f"❌ Ошибка\n\n{str(e)}"
    await message.answer(text, reply_markup=back_to_main_kb().as_markup())
    await state.clear()

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


@router.callback_query(F.data == "custom_algo")
async def custom_algo_menu(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    config = await custom_algo_db.get_by_tg_id(user_id)
    if config:
        text = f"{_format_custom_config(config)}\n\nМожно изменить конфигурацию."
        await safe_edit_message(callback, text, reply_markup=custom_algo_saved_kb().as_markup())
    else:
        await state.update_data(custom_draft=DEFAULT_CUSTOM_CONFIG.copy())
        await _show_custom_builder(callback, state)
    await callback.answer()


@router.callback_query(F.data == "custom_algo_edit")
async def custom_algo_edit(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    config = await custom_algo_db.get_by_tg_id(user_id)
    await state.update_data(custom_draft=normalize_custom_config(config or DEFAULT_CUSTOM_CONFIG.copy()))
    await _show_custom_builder(callback, state)
    await callback.answer()


@router.callback_query(F.data == "custom_toggle_direction")
async def custom_toggle_direction(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    draft["direction"] = "short" if draft.get("direction") == "long" else "long"
    await state.update_data(custom_draft=draft)
    await _show_custom_builder(callback, state)
    await callback.answer()


@router.callback_query(F.data.in_({"custom_toggle_trailing", "custom_toggle_stop_loss", "custom_toggle_breakeven"}))
async def custom_toggle_flags(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    draft = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    flag_map = {
        "custom_toggle_trailing": "use_trailing_stop",
        "custom_toggle_stop_loss": "use_stop_loss",
        "custom_toggle_breakeven": "use_breakeven",
    }
    field = flag_map[callback.data]
    draft[field] = not bool(draft.get(field, False))
    await state.update_data(custom_draft=draft)
    await _show_custom_builder(callback, state)
    await callback.answer()


@router.callback_query(F.data == "custom_set_order_amount")
async def custom_set_order_amount(callback: CallbackQuery, state: FSMContext):
    await safe_edit_message(callback, "Введите сумму сделки в USDT (0 = не фиксировать):")
    await state.set_state(TradingStates.waiting_for_custom_order_amount)
    await callback.answer()


@router.callback_query(F.data == "custom_next")
async def custom_next(callback: CallbackQuery, state: FSMContext):
    await _start_custom_step(callback, state)
    await callback.answer()


@router.callback_query(F.data == "custom_step_back")
async def custom_step_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    steps = data.get("custom_steps", [])
    idx = int(data.get("custom_step_index", 0))
    if not steps:
        await _show_custom_builder(callback, state)
        await callback.answer()
        return
    if idx <= 0:
        await _show_custom_builder(callback, state)
        await callback.answer()
        return
    prev_idx = idx - 1
    step_key, prompt = steps[prev_idx]
    await state.update_data(custom_step_index=prev_idx)
    await state.set_state(_step_to_state(step_key))
    await safe_edit_message(callback, f"📝 {prompt}", reply_markup=custom_step_back_kb().as_markup())
    await callback.answer()


@router.callback_query(F.data == "custom_confirm_back")
async def custom_confirm_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pending = data.get("custom_pending_config", DEFAULT_CUSTOM_CONFIG.copy())
    await state.update_data(custom_draft=pending)
    await _show_custom_builder(callback, state)
    await callback.answer()


@router.callback_query(F.data == "custom_confirm_accept")
async def custom_confirm_accept(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    pending = data.get("custom_pending_config")
    if not pending:
        await callback.answer("Нет конфигурации для сохранения", show_alert=True)
        return
    saved = await custom_algo_db.upsert_config(user_id, pending)
    await state.clear()
    await safe_edit_message(
        callback,
        f"✅ Конфигурация сохранена\n\n{_format_custom_config(saved)}",
        reply_markup=custom_algo_saved_kb().as_markup(),
    )
    await callback.answer("Сохранено")


@router.callback_query(F.data == "custom_algo_launch")
async def custom_algo_launch(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    config = await custom_algo_db.get_by_tg_id(user_id)
    if not config:
        await state.update_data(custom_draft=DEFAULT_CUSTOM_CONFIG.copy())
        await _show_custom_builder(callback, state)
        await callback.answer("Сначала создайте custom конфиг")
        return

    text = "🔴 Custom Algo\n\nВведите символ монеты (например BTCUSDT):"
    await safe_edit_message(callback, text, reply_markup=back_to_main_kb().as_markup())
    await state.set_state(TradingStates.waiting_for_custom_launch_symbol)
    await callback.answer()


@router.callback_query(F.data == "custom_launch_back_to_symbol")
async def custom_launch_back_to_symbol(callback: CallbackQuery, state: FSMContext):
    text = "🔴 Custom Algo\n\nВведите символ монеты (например BTCUSDT):"
    await safe_edit_message(callback, text, reply_markup=back_to_main_kb().as_markup())
    await state.set_state(TradingStates.waiting_for_custom_launch_symbol)
    await callback.answer()


@router.callback_query(F.data == "nomulti_short_3_limit")
async def nomulti_short_3_limit_start(callback: CallbackQuery, state: FSMContext):
    """Запрос символа для Short 3 limit (nomulti)."""
    text = "Введите символ (например BTCUSDT) для Short 3 limit (nomulti):"
    await safe_edit_message(
        callback,
        text,
        reply_markup=back_to_main_kb().as_markup(),
    )
    await state.update_data(algorithm="nomulti_short_3")
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
    algorithm = data.get("algorithm") or "nomulti_short_3"

    if algorithm == "hedge":
        url = f"{SERVER_URL}/hedge_long_short_bu_ts"
        algo_label = "Hedge long + short"
    else:
        url = f"{SERVER_URL}/nomulti_short_3_limit"
        algo_label = "Short 3 limit (nomulti)"

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


@router.message(TradingStates.waiting_for_custom_trailing_step)
async def process_custom_trailing_step(message: Message, state: FSMContext):
    await _handle_custom_step_input(message, state, "trailing_step_pct")


@router.message(TradingStates.waiting_for_custom_trailing_activate)
async def process_custom_trailing_activate(message: Message, state: FSMContext):
    await _handle_custom_step_input(message, state, "trailing_activate_pct")


@router.message(TradingStates.waiting_for_custom_stop_loss)
async def process_custom_stop_loss(message: Message, state: FSMContext):
    await _handle_custom_step_input(message, state, "stop_loss_pct")


@router.message(TradingStates.waiting_for_custom_breakeven)
async def process_custom_breakeven(message: Message, state: FSMContext):
    await _handle_custom_step_input(message, state, "breakeven_pct")


@router.message(TradingStates.waiting_for_custom_order_amount)
async def process_custom_order_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    steps = data.get("custom_steps")
    if steps:
        await _handle_custom_step_input(message, state, "order_amount_usdt")
        return
    raw = (message.text or "").strip().replace(",", ".")
    try:
        value = float(raw)
    except ValueError:
        await message.answer("Введите число, например: 10")
        return
    data = await state.get_data()
    draft = data.get("custom_draft", DEFAULT_CUSTOM_CONFIG.copy())
    draft["order_amount_usdt"] = None if value == 0 else value
    await state.update_data(custom_draft=draft)
    await message.answer(
        f"Сумма обновлена.\n\n{_format_custom_config(draft)}",
        reply_markup=custom_algo_config_kb(draft).as_markup(),
    )
    await state.set_state(None)


@router.message(TradingStates.waiting_for_custom_launch_symbol)
async def process_custom_launch_symbol(message: Message, state: FSMContext):
    symbol = message.text.strip().upper()
    user_id = message.from_user.id
    config = await custom_algo_db.get_by_tg_id(user_id)
    if not config:
        await message.answer("❌ Сначала создайте конфигурацию в Трейдинг -> Алгоритмы -> Custom")
        await state.clear()
        return
    await state.update_data(custom_launch_symbol=symbol)
    if config.get("order_amount_usdt") is None:
        await message.answer(
            "Введите сумму сделки в USDT для этого запуска:",
            reply_markup=custom_launch_amount_back_kb().as_markup(),
        )
        await state.set_state(TradingStates.waiting_for_custom_launch_amount)
        return
    await _launch_custom_algo(message, state, symbol, None)


@router.message(TradingStates.waiting_for_custom_launch_amount)
async def process_custom_launch_amount(message: Message, state: FSMContext):
    raw = (message.text or "").strip().replace(",", ".")
    try:
        amount = float(raw)
    except ValueError:
        await message.answer("Введите число, например: 10")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше 0")
        return
    data = await state.get_data()
    symbol = data.get("custom_launch_symbol")
    if not symbol:
        await message.answer("❌ Потерян символ. Запустите заново.")
        await state.clear()
        return
    await _launch_custom_algo(message, state, symbol, amount)


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
                    text = f"✅ Информация о позиции получена!\n\nСообщение: {data.get('result', '—')}"
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
