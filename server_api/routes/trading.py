from fastapi import APIRouter, HTTPException, Request
from server_api.schemas import SymbolRequest
from logger_config import setup_logger
from celery_app.tasks.short_3_limit import short_3_limit
from bybit_logic.bybit_func import session, stop_trade, position
from server_api.utils import validate_and_clean_symbol
from config import USE_DEMO

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/short_3_limit")
async def short_3_limit_endpoint(request: Request):
    """Запускает алгоритм short для символа (принимает текст)"""
    try:
        # Получаем тело запроса как текст
        body = await request.body()
        symbol = body.decode('utf-8').strip().upper()
        symbol = validate_and_clean_symbol(symbol)
        logger.info(f"🔍 Валидированный символ: {symbol}")

        if not symbol:
            raise HTTPException(status_code=400, detail="Символ не может быть пустым")
        
        task = short_3_limit.delay(symbol)
        logger.info(f"🚀 Запущена задача для {symbol}, task_id: {task.id}")
        return {
            "task_id": task.id,
            "symbol": symbol,
            "status": "started"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_trading_by_symbol")
async def stop_trading_by_symbol_endpoint(request: SymbolRequest):
    """Останавливает алгоритм short для символа"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        symbol = validate_and_clean_symbol(request.symbol)
        symbol = symbol.upper()
        stop_trade.stop_trading_by_symbol(symbol, http_session)
        return {"message": "Алгоритм остановлен"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки алгоритма: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_trading_all")
async def stop_trading_all():
    """Останавливает все алгоритмы торговли"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        stop_trade.stop_all_trading(http_session)
        return {"message": "Все алгоритмы остановлены"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки всех алгоритмов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/result_position_info_by_symbol")
async def result_position_info_by_symbol(request: SymbolRequest):
    """Получает информацию о позиции"""
    try:
        logger.info(f"🔍 USE_DEMO из config: {USE_DEMO} (тип: {type(USE_DEMO)})")  # ✅ Для отладки
        http_session = session.create_session(use_demo=USE_DEMO)
        symbol = validate_and_clean_symbol(request.symbol)
        symbol = symbol.upper()
        result = position.result_position_info(symbol, http_session)
        return {"result": result}
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о позиции: {e}")
        raise HTTPException(status_code=500, detail=str(e))