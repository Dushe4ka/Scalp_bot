from fastapi import APIRouter, HTTPException, Request
from server_api.schemas import SymbolRequest
from logger_config import setup_logger
from bybit_logic.bybit_func import account
from bybit_logic.bybit_func.session import create_session
from config import USE_DEMO

router = APIRouter()
logger = setup_logger(__name__)

session = create_session(use_demo=USE_DEMO)

@router.get("/futures_balance")
async def get_futures_balance():
    try:
        balance = float(account.get_futures_balance(session))
        balance = round(balance, 2)
        logger.info(f"Futures balance: {balance}")
        return {"balance": balance}
    except Exception as e:
        logger.error(f"Error getting futures balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))
