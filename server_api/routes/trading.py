from fastapi import APIRouter, HTTPException
from server_api.schemas import SymbolRequest
from logger_config import setup_logger
from celery_app.tasks.short_3_limit import short_3_limit
from bybit_logic.bybit_func import session, stop_trade, position

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/short_3_limit")
async def short_3_limit_endpoint(request: SymbolRequest):
    """Запускает алгоритм short для символа"""
    try:
        task = short_3_limit.delay(request.symbol.upper())  # Передаем symbol
        logger.info(f"🚀 Запущена задача для {request.symbol.upper()}, task_id: {task.id}")
        return {
            "task_id": task.id,
            "symbol": request.symbol.upper(),
            "status": "started"
        }
    except Exception as e:
        logger.error(f"❌ Ошибка запуска задачи: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_trading_by_symbol")
async def stop_trading_by_symbol_endpoint(request: SymbolRequest):
    """Останавливает алгоритм short для символа"""
    try:
        http_session = session.create_session()
        stop_trade.stop_trading_by_symbol(request.symbol.upper(), http_session)
        return {"message": "Алгоритм остановлен"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки алгоритма: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop_trading_all")
async def stop_trading_all():
    """Останавливает все алгоритмы торговли"""
    try:
        http_session = session.create_session()
        stop_trade.stop_all_trading(http_session)
        return {"message": "Все алгоритмы остановлены"}
    except Exception as e:
        logger.error(f"❌ Ошибка остановки всех алгоритмов: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/result_position_info_by_symbol")
async def result_position_info_by_symbol(request: SymbolRequest):
    """Получает информацию о позиции"""
    try:
        http_session = session.create_session()
        result = position.result_position_info(request.symbol.upper(), http_session)
        return {"result": result}
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о позиции: {e}")
        raise HTTPException(status_code=500, detail=str(e))