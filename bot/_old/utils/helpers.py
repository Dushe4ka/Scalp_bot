from aiogram.types import CallbackQuery, InlineKeyboardMarkup
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from database.subscribers import get_subscribers
from bot.utils.misc import bot
from bot.config import TELEGRAM_BOT_TOKEN
from logger_config import setup_logger
import requests
import time

logger = setup_logger(__name__)

async def safe_edit_message(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None
) -> bool:
    """
    Безопасное редактирование сообщения с обработкой ошибки 'message is not modified'
    
    Эта функция предотвращает ошибку TelegramBadRequest, которая возникает,
    когда пытаемся отредактировать сообщение с тем же текстом и клавиатурой.
    
    Args:
        callback: CallbackQuery объект
        text: Текст сообщения
        reply_markup: Клавиатура (опционально)
        
    Returns:
        bool: True если сообщение успешно отредактировано, False если произошла ошибка "message is not modified"
    """
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=reply_markup
        )
        return True
    except TelegramBadRequest as e:
        # Игнорируем ошибку "message is not modified"
        error_message = str(e).lower()
        if "message is not modified" in error_message:
            logger.debug(f"Сообщение не изменено (user_id: {callback.from_user.id}, message_id: {callback.message.message_id})")
            return False
        # Для других ошибок логируем и пробрасываем дальше
        logger.error(f"Ошибка редактирования сообщения: {e} (user_id: {callback.from_user.id})")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании сообщения: {e} (user_id: {callback.from_user.id})")
        raise

async def send_to_subscribers_async(text: str) -> dict:
    """
    Асинхронная версия отправки сообщений подписчикам
    Используется в асинхронном контексте (бот handlers)
    
    Args:
        text: Текст сообщения для отправки
        
    Returns:
        dict: Статистика отправки с ключами:
            - total: общее количество подписчиков
            - sent: количество успешно отправленных сообщений
            - failed: количество неудачных отправок
            - errors: список ошибок с user_id
    """
    subscribers = get_subscribers()
    total = len(subscribers)
    sent = 0
    failed = 0
    errors = []
    
    if total == 0:
        logger.info("Нет подписчиков для отправки сообщения")
        return {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "errors": []
        }
    
    logger.info(f"Начало рассылки сообщения {total} подписчикам")
    
    for user_id in subscribers:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=text
            )
            sent += 1
            logger.debug(f"Сообщение отправлено подписчику {user_id}")
        except TelegramForbiddenError:
            # Пользователь заблокировал бота
            failed += 1
            errors.append({"user_id": user_id, "error": "User blocked the bot"})
            logger.warning(f"Пользователь {user_id} заблокировал бота")
        except TelegramAPIError as e:
            # Другие ошибки API Telegram
            failed += 1
            errors.append({"user_id": user_id, "error": str(e)})
            logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {e}")
        except Exception as e:
            # Неожиданные ошибки
            failed += 1
            errors.append({"user_id": user_id, "error": str(e)})
            logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
    
    logger.info(f"Рассылка завершена: отправлено {sent} из {total}, ошибок: {failed}")
    
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "errors": errors
    }


def send_to_subscribers_sync(text: str) -> dict:
    """
    СИНХРОННАЯ версия отправки сообщений подписчикам
    Используется в Celery задачах и других синхронных контекстах
    Args:
        text: Текст сообщения для отправки
        
    Returns:
        dict: Статистика отправки с ключами:
            - total: общее количество подписчиков
            - sent: количество успешно отправленных сообщений
            - failed: количество неудачных отправок
            - errors: список ошибок с user_id
    """
    subscribers = get_subscribers()
    total = len(subscribers)
    sent = 0
    failed = 0
    errors = []
    
    if total == 0:
        logger.info("Нет подписчиков для отправки сообщения")
        return {
            "total": 0,
            "sent": 0,
            "failed": 0,
            "errors": []
        }
    
    logger.info(f"Начало синхронной рассылки сообщения {total} подписчикам")
    
    # Telegram Bot API endpoint
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    for user_id in subscribers:
        try:
            # Прямой HTTP запрос к Telegram Bot API
            response = requests.post(
                api_url,
                json={
                    "chat_id": user_id,
                    "text": text,
                    "parse_mode": "HTML"  # Опционально, для форматирования
                },
                timeout=10  # Таймаут 10 секунд
            )
            
            response.raise_for_status()
            result = response.json()
            
            if result.get("ok"):
                sent += 1
                logger.debug(f"Сообщение отправлено подписчику {user_id}")
            else:
                # Telegram вернул ошибку
                error_description = result.get("description", "Unknown error")
                failed += 1
                errors.append({"user_id": user_id, "error": error_description})
                
                # Если пользователь заблокировал бота, логируем отдельно
                if "blocked" in error_description.lower() or "forbidden" in error_description.lower():
                    logger.warning(f"Пользователь {user_id} заблокировал бота")
                else:
                    logger.error(f"Ошибка отправки сообщения пользователю {user_id}: {error_description}")
            
            # Небольшая задержка чтобы не превысить rate limits Telegram API
            # Telegram позволяет до 30 сообщений в секунду
            if total > 30:
                time.sleep(0.05)  # 50ms задержка = ~20 сообщений в секунду
                
        except requests.exceptions.Timeout:
            failed += 1
            errors.append({"user_id": user_id, "error": "Request timeout"})
            logger.error(f"Таймаут при отправке сообщения пользователю {user_id}")
        except requests.exceptions.RequestException as e:
            failed += 1
            errors.append({"user_id": user_id, "error": str(e)})
            logger.error(f"Ошибка HTTP запроса для пользователя {user_id}: {e}")
        except Exception as e:
            failed += 1
            errors.append({"user_id": user_id, "error": str(e)})
            logger.error(f"Неожиданная ошибка при отправке сообщения пользователю {user_id}: {e}")
    
    logger.info(f"Синхронная рассылка завершена: отправлено {sent} из {total}, ошибок: {failed}")
    
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "errors": errors
    }

