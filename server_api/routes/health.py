from fastapi import APIRouter
from logger_config import setup_logger

router = APIRouter()
logger = setup_logger(__name__)

@router.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "scalp_bot_api"
    }