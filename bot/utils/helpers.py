import asyncio
from typing import Any
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.types import InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from database.subscribers import get_subscribers
from bot.utils.misc import bot
from config import TELEGRAM_BOT_TOKEN, ADMIN_IDS, TECH_SUPPORT_ID
from logger_config import setup_logger
from bybit_logic.bybit_func import account, calculator
from bybit_logic.bybit_func.session import create_session
from config import USE_DEMO
import requests
import time

logger = setup_logger(__name__)

async def safe_edit_message(
    callback: CallbackQuery | Message,
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
    if isinstance(callback, CallbackQuery):
        target_message = callback.message
        user_id = callback.from_user.id
    else:
        target_message = callback
        user_id = callback.from_user.id

    try:
        await target_message.edit_text(
            text=text,
            reply_markup=reply_markup
        )
        return True
    except TelegramBadRequest as e:
        # Игнорируем ошибку "message is not modified"
        error_message = str(e).lower()
        if "message is not modified" in error_message:
            logger.debug(f"Сообщение не изменено (user_id: {user_id}, message_id: {target_message.message_id})")
            return False
        # Для других ошибок логируем и пробрасываем дальше
        logger.error(f"Ошибка редактирования сообщения: {e} (user_id: {user_id})")
        raise
    except Exception as e:
        logger.error(f"Неожиданная ошибка при редактировании сообщения: {e} (user_id: {user_id})")
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


def send_to_subscribers_sync(text: str, *, bot_token: str | None = None) -> dict:
    """
    СИНХРОННАЯ версия отправки сообщений подписчикам
    Используется в Celery задачах и других синхронных контекстах
    Args:
        text: Текст сообщения для отправки
        bot_token: токен бота Telegram; по умолчанию TELEGRAM_BOT_TOKEN из config.
                   Для nomulti задайте тот же токен, что у бота, через который подписывались
                   (например через env CELERY_SUBSCRIBERS_BOT_TOKEN в notifications).
        
    Returns:
        dict: Статистика отправки с ключами:
            - total: общее количество подписчиков
            - sent: количество успешно отправленных сообщений
            - failed: количество неудачных отправок
            - errors: список ошибок с user_id
    """
    token = (bot_token or TELEGRAM_BOT_TOKEN or "").strip()
    if not token:
        logger.error("send_to_subscribers_sync: не задан bot_token и TELEGRAM_BOT_TOKEN")
        return {"total": 0, "sent": 0, "failed": 0, "errors": [{"error": "missing_bot_token"}]}
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
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    for user_id in subscribers:
        delivered = False
        last_error = ""
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
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
                    delivered = True
                    logger.debug(f"Сообщение отправлено подписчику {user_id} (попытка {attempt})")
                    break

                error_description = result.get("description", "Unknown error")
                last_error = error_description
                # Ошибки прав доступа не ретраим, это не временная проблема.
                if "blocked" in error_description.lower() or "forbidden" in error_description.lower():
                    logger.warning(f"Пользователь {user_id} заблокировал бота")
                    break

                logger.error(
                    f"Ошибка отправки сообщения пользователю {user_id} (попытка {attempt}/{max_attempts}): "
                    f"{error_description}"
                )
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                logger.error(
                    f"Таймаут при отправке сообщения пользователю {user_id} "
                    f"(попытка {attempt}/{max_attempts})"
                )
            except requests.exceptions.RequestException as e:
                last_error = str(e)
                logger.error(
                    f"Ошибка HTTP запроса для пользователя {user_id} "
                    f"(попытка {attempt}/{max_attempts}): {e}"
                )
            except Exception as e:
                last_error = str(e)
                logger.error(
                    f"Неожиданная ошибка при отправке сообщения пользователю {user_id} "
                    f"(попытка {attempt}/{max_attempts}): {e}"
                )

            if attempt < max_attempts:
                # Небольшой backoff перед следующей попыткой.
                time.sleep(0.6 * attempt)

        if not delivered:
            failed += 1
            errors.append({"user_id": user_id, "error": last_error or "Unknown error"})

        # Небольшая задержка чтобы не превысить rate limits Telegram API
        # Telegram позволяет до 30 сообщений в секунду
        if total > 30:
            time.sleep(0.05)  # 50ms задержка = ~20 сообщений в секунду
    
    logger.info(f"Синхронная рассылка завершена: отправлено {sent} из {total}, ошибок: {failed}")
    
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "errors": errors
    }

async def send_info_payment_to_admin(payment_id: str, user_id: int, username: str) -> bool:
    """
    Отправка информации о платеже:
    1) в техподдержку (если задан TECH_SUPPORT_ID),
    2) затем администратору.
    """
    from bot.callback_data.admin_lists import AdminOpenUserCb

    text = f"Пользователь {username} ({user_id}) Оплатил подписку. ID платежа: {payment_id}"
    admin_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Открыть профиль пользователя",
                    callback_data=AdminOpenUserCb(tg_id=int(user_id)).pack(),
                )
            ]
        ]
    )
    support_ok = True
    admin_ok = True

    try:
        if TECH_SUPPORT_ID:
            await bot.send_message(
                chat_id=TECH_SUPPORT_ID,
                text=text,
                reply_markup=admin_kb,
            )
        else:
            logger.warning("TECH_SUPPORT_ID не задан, отправка сообщения в техподдержку пропущена")
    except Exception as e:
        support_ok = False
        logger.error(f"Ошибка при отправке информации о платеже в техподдержку: {e}")

    try:
        for admin_id in sorted(ADMIN_IDS):
            await bot.send_message(chat_id=admin_id, text=text, reply_markup=admin_kb)
        if not ADMIN_IDS:
            logger.warning("ADMIN_IDS пуст — отправка сообщения администратору пропущена")
            admin_ok = False
    except Exception as e:
        admin_ok = False
        logger.error(f"Ошибка при отправке информации о платеже администратору: {e}")

    return support_ok and admin_ok


def extract_user_api_credentials(user: dict[str, Any]) -> tuple[str, str]:
    bybit_data = user.get("bybit_data") or {}
    api_key = str(bybit_data.get("api_key") or "").strip()
    api_secret = str(bybit_data.get("api_secret") or "").strip()
    return api_key, api_secret


async def get_recommended_trade_amount(user: dict[str, Any]) -> float | None:
    api_key, api_secret = extract_user_api_credentials(user)
    if not api_key or not api_secret:
        return None

    try:
        session = create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)
        balance = await asyncio.to_thread(account.get_futures_balance, session)
        recommended = calculator.calculate_max_permitted_price(float(balance))
        return round(float(recommended), 2)
    except Exception as e:
        logger.warning("Не удалось рассчитать рекомендованную сумму сделки: %s", e)
        return None


async def notify_user_telegram(bot, tg_id: int, text: str) -> bool:
    """Отправляет личное уведомление пользователю в Telegram."""
    try:
        await bot.send_message(chat_id=int(tg_id), text=text)
        return True
    except Exception as e:
        logger.error("Не удалось отправить уведомление tg_id=%s: %s", tg_id, e)
        return False
