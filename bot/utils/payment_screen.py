"""Экран оплаты подписки: текст + QR-код."""
from __future__ import annotations

from pathlib import Path

from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardMarkup

from logger_config import setup_logger

logger = setup_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PAYMENT_QR_CANDIDATES = (
    _PROJECT_ROOT / "_images" / "qr_code_pay.png",
    _PROJECT_ROOT / "_images" / "qr_code_pay.jpg",
)


def resolve_payment_qr_image() -> Path | None:
    for path in _PAYMENT_QR_CANDIDATES:
        if path.is_file():
            return path
    return None


async def send_payment_info_screen(
    callback: CallbackQuery,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    """Показать инструкцию по оплате с QR (фото) или текстом, если файла нет."""
    await callback.answer()
    chat_id = callback.message.chat.id

    try:
        await callback.message.delete()
    except Exception as e:
        logger.debug("Не удалось удалить предыдущее сообщение оплаты: %s", e)

    qr_path = resolve_payment_qr_image()
    if qr_path is not None:
        await callback.bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(qr_path),
            caption=text,
            reply_markup=reply_markup,
        )
        return

    logger.warning("QR для оплаты не найден в _images/, отправляем только текст")
    await callback.bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
    )
