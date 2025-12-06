from fastapi import APIRouter, Request
from logger_config import setup_logger
import json

router = APIRouter()
logger = setup_logger(__name__)

@router.post("/monitoring")
async def monitoring(request: Request):
    """Принимает любой POST запрос и логирует его тело"""
    try:
        body = await request.body()
        body_text = body.decode('utf-8')
        
        # Пытаемся распарсить как JSON для красивого вывода
        try:
            data = json.loads(body_text)
            logger.info(f"📊 MONITORING (JSON): {json.dumps(data, indent=2, ensure_ascii=False)}")
        except:
            # Если не JSON, логируем как текст
            logger.info(f"📊 MONITORING (TEXT): {body_text}")
        
        return {"logged": True}
    except Exception as e:
        logger.error(f"❌ Ошибка в monitoring: {e}")
        return {"logged": False, "error": str(e)}