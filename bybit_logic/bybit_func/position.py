from pybit.unified_trading import HTTP
from logger_config import setup_logger
from typing import Optional, Dict, Any
from datetime import datetime

logger = setup_logger(__name__)


def get_positions_by_symbol(session: HTTP, symbol: str) -> dict:
    """
    Получает позиции по символу
    """
    try:    
        return session.get_positions(
                category="linear",
                symbol=symbol
                )
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        return None

def get_last_position_by_symbol(session: HTTP, symbol: str) -> dict:
    """
    Получает последнюю позицию по символу
    """
    positions = get_positions_by_symbol(session, symbol)
    if positions and positions.get('result', {}).get('list'):
        return positions['result']['list'][0]
    else:
        return None

def get_all_positions(session: HTTP) -> dict:
    """
    Получает все позиции
    """
    try:
        return session.get_positions(
            category="linear",
            settleCoin="USDT",
        )
    except Exception as e:
        logger.error(f"Error getting all positions: {e}")
        return None

def if_position_open(session: HTTP, symbol: str) -> bool:
    """
    Проверяет, открыта ли позиция по символу
    """
    positions = get_positions_by_symbol(session, symbol)
    
    if positions and positions.get('result', {}).get('list'):
        position_info = positions['result']['list'][0]
        
        # ✅ ПРОВЕРКА: Позиция открыта только если размер больше 0
        position_size = float(position_info.get('size', 0))
        if position_size > 0:
            return True
        else:
            return False


def get_last_position_info(session: HTTP, symbol: str) -> Optional[Dict[str, Any]]:
    """
    Получает информацию о последней позиции (открытой или закрытой) для указанного символа
    
    Args:
        session: HTTP сессия Bybit
        symbol: Торговая пара (например: "BTCUSDT")
    
    Returns:
        dict: Словарь с информацией о позиции или None, если позиция не найдена
        
        Структура возвращаемых данных:
        {
            'symbol': str,              # Символ (например: "BTCUSDT")
            'side': str,                # Сторона позиции ("Buy" или "Sell")
            'size': float,              # Размер позиции
            'entry_price': float,       # Цена входа
            'exit_price': Optional[float],  # Цена выхода (None если позиция открыта)
            'pnl_usdt': float,          # Прибыль/убыток в USDT
            'open_time': Optional[datetime],  # Время открытия позиции
            'close_time': Optional[datetime], # Время закрытия позиции (None если открыта)
            'is_open': bool             # True если позиция открыта, False если закрыта
        }
    """
    try:
        symbol = symbol.upper()
        
        # 1. Сначала проверяем текущую позицию (может быть открыта)
        position_data = get_positions_by_symbol(session, symbol)
        
        if position_data and position_data.get('result', {}).get('list'):
            position_info = position_data['result']['list'][0]
            position_size = float(position_info.get('size', 0))
            
            # Если позиция открыта
            if position_size > 0:
                created_time = int(position_info.get('createdTime', 0)) / 1000
                open_time = datetime.fromtimestamp(created_time) if created_time else None
                
                return {
                    'symbol': symbol,
                    'side': position_info.get('side', ''),
                    'size': position_size,
                    'entry_price': float(position_info.get('avgPrice', 0)),
                    'exit_price': None,
                    'pnl_usdt': float(position_info.get('unrealisedPnl', 0)) if position_info.get('unrealisedPnl') else 0.0,
                    'open_time': open_time,
                    'close_time': None,
                    'is_open': True
                }
        
        # 2. Если позиция закрыта, получаем информацию из истории закрытых PnL
        closed_pnl = session.get_closed_pnl(
            category="linear",
            symbol=symbol,
            limit=1  # Только последняя закрытая позиция
        )
        
        if closed_pnl and closed_pnl.get('result', {}).get('list'):
            pnl_list = closed_pnl['result']['list']
            
            if pnl_list:
                pnl_item = pnl_list[0]  # Последняя закрытая позиция
                
                created_time = int(pnl_item.get('createdTime', 0)) / 1000
                updated_time = int(pnl_item.get('updatedTime', 0)) / 1000
                
                open_time = datetime.fromtimestamp(created_time) if created_time else None
                close_time = datetime.fromtimestamp(updated_time) if updated_time else None
                
                return {
                    'symbol': pnl_item.get('symbol', symbol),
                    'side': pnl_item.get('side', ''),
                    'size': float(pnl_item.get('qty', 0)),
                    'entry_price': float(pnl_item.get('avgEntryPrice', 0)),
                    'exit_price': float(pnl_item.get('avgExitPrice', 0)),
                    'pnl_usdt': float(pnl_item.get('closedPnl', 0)),
                    'open_time': open_time,
                    'close_time': close_time,
                    'is_open': False
                }
        
        # Если ничего не найдено
        return None
        
    except Exception as e:
        logger.error(f"Ошибка при получении информации о последней позиции для {symbol}: {e}")
        return None

def result_position_info(symbol: str, session: HTTP) -> Optional[str]:
    """
    Формирует и возвращает итоговую информацию о позиции в виде текста
    
    Args:
        symbol: Торговая пара (например: "BTCUSDT")
        session: HTTP сессия Bybit
    
    Returns:
        str: Компактный текст с информацией о позиции или None, если позиция не найдена
    """
    position_info = get_last_position_info(session, symbol)

    if position_info:
        lines = []
        lines.append(f"📊 Позиция: {position_info['symbol']}")
        
        # Статус
        status = "🟢 Открыта" if position_info['is_open'] else "🔴 Закрыта"
        lines.append(f"Статус: {status}")
        
        # Сторона
        side_text = "Лонг" if position_info['side'] == 'Buy' else "Шорт"
        lines.append(f"Сторона: {side_text}")
        
        # Размер и цены
        lines.append(f"Размер: {position_info['size']}")
        lines.append(f"Цена входа: {position_info['entry_price']:.8g}")
        
        if position_info['exit_price']:
            lines.append(f"Цена выхода: {position_info['exit_price']:.8g}")
        
        # Время
        if position_info['open_time']:
            lines.append(f"Открыта: {position_info['open_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if position_info['close_time']:
            lines.append(f"Закрыта: {position_info['close_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        # PnL
        pnl = position_info['pnl_usdt']
        if pnl > 0:
            lines.append(f"💰 PnL: +{pnl:.2f} USDT")
        elif pnl < 0:
            lines.append(f"❌ PnL: {pnl:.2f} USDT")
        else:
            lines.append(f"⚪ PnL: {pnl:.2f} USDT")
        
        # Изменение цены (только для закрытых позиций)
        if not position_info['is_open'] and position_info['entry_price'] > 0:
            entry = position_info['entry_price']
            exit_price = position_info['exit_price']
            
            if exit_price and exit_price > 0:
                if position_info['side'] == 'Buy':
                    percent_change = ((exit_price - entry) / entry) * 100
                else:  # Sell
                    percent_change = ((entry - exit_price) / entry) * 100
                
                lines.append(f"📈 Изменение: {percent_change:+.2f}%")
        
        return "\n".join(lines)
        
    else:
        return "❌ Позиция не найдена"


def result_position_info_data(symbol: str, session: HTTP) -> Optional[Dict[str, Any]]:
    """
    Возвращает структурированные данные по последней позиции.
    """
    return get_last_position_info(session, symbol)

def switch_position_mode(session: HTTP, symbol: str, position_mode: int = 3) -> None:
    """
    Переключает режим позиции для linear-символа (UTA V5).
    mode: 0 = one-way, 3 = hedge.
    """
    try:
        symbol = symbol.upper()
        session.switch_position_mode(
            category="linear",
            symbol=symbol,
            # Bybit V5 ожидает ключ mode (0 = one-way, 3 = hedge mode).
            mode=position_mode,
        )
    except Exception as e:
        error_text = str(e)
        # Bybit: 110025 = Position mode is not modified (режим уже установлен).
        if "110025" in error_text or "position mode is not modified" in error_text.lower():
            logger.info("Режим позиции для %s уже установлен (mode=%s), продолжаю", symbol, position_mode)
            return
        logger.error(f"Ошибка при переключении режима позиции: {e}")
        raise Exception(f"Ошибка при переключении режима позиции: {e}") from e


def try_switch_linear_one_way(session: HTTP, symbol: str) -> bool:
    """
    Пытается перевести символ в one-way (mode=0) перед новой позицией.
    Не бросает исключения: при открытых позициях или ограничениях биржи вернёт False.
    """
    try:
        switch_position_mode(session, symbol, 0)
        logger.info("Режим позиции для %s: one-way (mode=0)", symbol.upper())
        return True
    except Exception as e:
        logger.warning(
            "Не удалось переключить %s в one-way (часто из-за открытых позиций по символу): %s — "
            "продолжаю с текущим режимом; при hedge ордер уйдёт с positionIdx.",
            symbol.upper(),
            e,
        )
        return False

def set_leverage(
    session: HTTP,
    symbol: str,
    leverage: int = 10,
    *,
    category: str = "linear",
    buy_leverage: int | None = None,
    sell_leverage: int | None = None,
    allow_lower_if_exceeds_max: bool = False,
) -> Dict[str, Any]:
    """
    Устанавливает кредитное плечо
    """
    try:
        symbol = symbol.upper()
        requested_buy = float(buy_leverage if buy_leverage is not None else leverage)
        requested_sell = float(sell_leverage if sell_leverage is not None else leverage)
        max_lev = get_max_leverage(session, symbol, category=category)
        final_buy = requested_buy
        final_sell = requested_sell
        was_capped = False

        # Если удалось получить биржевой лимит — проверяем ограничение.
        if max_lev is not None:
            if final_buy > max_lev or final_sell > max_lev:
                if not allow_lower_if_exceeds_max:
                    logger.warning(
                        "Запрошенное плечо для %s превышает maxLeverage=%s. Строгий режим: установка отклонена",
                        symbol,
                        max_lev,
                    )
                    return {
                        "ok": False,
                        "symbol": symbol,
                        "error_type": "leverage_too_high",
                        "error": f"Requested leverage exceeds max leverage {max_lev}",
                        "requested_buy": requested_buy,
                        "requested_sell": requested_sell,
                        "max_leverage": max_lev,
                    }
                was_capped = True
                logger.warning(
                    "Запрошенное плечо для %s превышает maxLeverage=%s, ограничиваю до лимита (гибкий режим)",
                    symbol,
                    max_lev,
                )
                final_buy = min(final_buy, max_lev)
                final_sell = min(final_sell, max_lev)

        session.set_leverage(
            category=category,
            symbol=symbol,
            # Bybit V5 + pybit ожидают camelCase-ключи и строковые значения.
            buyLeverage=str(final_buy),
            sellLeverage=str(final_sell),
        )
        logger.info(
            "✅ Плечо установлено для %s: buy=%s sell=%s (requested buy=%s sell=%s max=%s)",
            symbol,
            str(final_buy),
            str(final_sell),
            str(requested_buy),
            str(requested_sell),
            str(max_lev),
        )
        return {
            "ok": True,
            "symbol": symbol,
            "requested_buy": requested_buy,
            "requested_sell": requested_sell,
            "applied_buy": final_buy,
            "applied_sell": final_sell,
            "max_leverage": max_lev,
            "was_capped": was_capped,
        }
    except Exception as e:
        error_text = str(e)
        # Bybit: ErrCode 110043 = leverage not modified (значение уже установлено).
        if "110043" in error_text or "leverage not modified" in error_text.lower():
            logger.info(
                "Плечо для %s уже установлено (buy=%s, sell=%s), продолжаю без ошибки",
                symbol,
                str(final_buy),
                str(final_sell),
            )
            return {
                "ok": True,
                "symbol": symbol,
                "requested_buy": requested_buy,
                "requested_sell": requested_sell,
                "applied_buy": final_buy,
                "applied_sell": final_sell,
                "max_leverage": max_lev,
                "was_capped": was_capped,
                "not_modified": True,
            }
        logger.error(f"Ошибка при установке кредитного плеча: {e}")
        return {
            "ok": False,
            "symbol": symbol,
            "error": str(e),
        }


def set_isolated_margin(
    session: HTTP,
    symbol: str,
    category: str = "linear",
    buy_leverage: int = 10,
    sell_leverage: int = 10,
) -> None:
    """
    Включает изолированную маржу для Unified Trading Account (UTA).

    На UTA режим cross/isolated задаётся на уровне **всего аккаунта**, а не через
    ``/v5/position/switch-isolated`` (``switch_margin_mode``) по символу — для UTA
    эта ручка даёт ErrCode 100028 «unified account is forbidden».

    Рабочий путь: ``POST /v5/account/set-margin-mode`` с ``setMarginMode=ISOLATED_MARGIN``
    (в pybit: ``session.set_margin_mode``). Параметры ``category`` / ``buy_leverage`` /
    ``sell_leverage`` оставлены в сигнатуре для совместимости вызовов; плечо после
    переключения режима задаётся отдельно через ``set_leverage``.

    Документация: https://bybit-exchange.github.io/docs/v5/account/set-margin-mode
    """
    set_account_margin_mode(session, symbol, desired_mode="ISOLATED")


def set_account_margin_mode(session: HTTP, symbol: str, desired_mode: str = "CROSS") -> None:
    """
    Переключает режим маржи аккаунта UTA между CROSS и ISOLATED.

    Args:
        session: HTTP-сессия pybit
        symbol: Символ (только для лог-контекста)
        desired_mode: CROSS/REGULAR или ISOLATED
    """
    symbol = symbol.upper()
    desired_raw = (desired_mode or "CROSS").strip().upper()

    mode_aliases = {
        "CROSS": "REGULAR_MARGIN",
        "REGULAR": "REGULAR_MARGIN",
        "REGULAR_MARGIN": "REGULAR_MARGIN",
        "ISOLATED": "ISOLATED_MARGIN",
        "ISOLATED_MARGIN": "ISOLATED_MARGIN",
    }
    target_mode = mode_aliases.get(desired_raw)
    if target_mode is None:
        raise ValueError(
            f"Неизвестный режим маржи '{desired_mode}'. Используйте CROSS/REGULAR или ISOLATED"
        )

    try:
        info = session.get_account_info()
        if info.get("retCode") != 0:
            raise Exception(f"get_account_info: {info}")

        current_mode = (info.get("result") or {}).get("marginMode")
        if current_mode == target_mode:
            logger.info("Режим маржи уже %s (%s), пропуск", target_mode, symbol)
            return

        session.set_margin_mode(setMarginMode=target_mode)
        logger.info(
            "✅ Аккаунт переведён в %s (символ в контексте: %s)",
            target_mode,
            symbol,
        )
    except Exception as e:
        logger.error(
            "Ошибка при переключении режима маржи для %s в %s: %s",
            symbol,
            target_mode,
            e,
        )
        raise Exception(
            f"Ошибка при переключении режима маржи для {symbol} в {target_mode}: {e}"
        ) from e


def get_max_leverage(session: HTTP, symbol: str, category: str = "linear") -> Optional[float]:
    """
    Возвращает максимально допустимое плечо для инструмента.

    Bybit V5: /v5/market/instruments-info -> leverageFilter.maxLeverage
    """
    try:
        symbol = symbol.upper()
        data = session.get_instruments_info(
            category=category,
            symbol=symbol,
        )
        instruments = data.get("result", {}).get("list", [])
        if not instruments:
            logger.warning("Инструмент не найден для maxLeverage: %s", symbol)
            return None

        leverage_filter = instruments[0].get("leverageFilter") or {}
        max_leverage_raw = leverage_filter.get("maxLeverage")
        if max_leverage_raw is None:
            logger.warning("В ответе нет leverageFilter.maxLeverage для %s", symbol)
            return None

        return float(max_leverage_raw)
    except Exception as e:
        logger.error("Ошибка при получении maxLeverage для %s: %s", symbol, e)
        return None
