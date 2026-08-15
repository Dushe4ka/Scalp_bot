import os
import dotenv

dotenv.load_dotenv()

# ✅ Преобразуем строку из .env в булево значение
USE_DEMO_STR = os.getenv("USE_DEMO", "False").strip().lower()
USE_DEMO = USE_DEMO_STR in ("true", "1", "yes")

# Режим маржи аккаунта для UTA:
# - CROSS / REGULAR / REGULAR_MARGIN
# - ISOLATED / ISOLATED_MARGIN
TRADING_MARGIN_MODE = (os.getenv("MARGIN_MODE", "CROSS") or "CROSS").strip().upper()

# Поддержка двух форматов env-ключей:
# - новый: MONGO_URI / MONGO_DB
# - legacy: MONGODB_URI / MONGODB_DB
MONGO_URI = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
MONGO_DB = os.getenv("MONGO_DB") or os.getenv("MONGODB_DB") or "scalp_bot"

# Данные для Telegram бота
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
URL_TGCHANNEL = os.getenv("URL_TGCHANNEL")
URL_PAYMENT = os.getenv("URL_PAYMENT")
URL_TECH_SUPPORT = os.getenv("URL_TECH_SUPPORT")
TECH_SUPPORT_ID = os.getenv("TECH_SUPPORT_ID")


def _parse_admin_id_list(raw: str | None) -> set[int]:
    """Парсит Telegram ID из строки вида '123' или '123,456,789'."""
    out: set[int] = set()
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


# Доступ к /admin и админ-уведомления: один или несколько ID через запятую
ADMIN_IDS = _parse_admin_id_list(os.getenv("ADMIN_IDS"))


def resolve_nomulti_tg_id() -> int:
    """Telegram ID для nomulti: NOMULTI_TG_ID или первый ID из ADMIN_IDS."""
    raw = (os.getenv("NOMULTI_TG_ID") or "").strip()
    if raw.isdigit():
        return int(raw)
    if ADMIN_IDS:
        return min(ADMIN_IDS)
    return 0


# Локальный URL для внутренних запросов проекта (бот -> API, админка -> API)
LOCAL_SERVER_URL = os.getenv("LOCAL_SERVER_URL", "http://127.0.0.1:8050")

# Публичный URL (для уведомлений/показа внешних эндпоинтов)
SERVER_URL = os.getenv("SERVER_URL", LOCAL_SERVER_URL)

# Рекомендуемая сумма сделки: процент от futures-баланса (1.75 = 1,75%)
RECOMMENDED_TRADE_AMOUNT_PERCENT = float(os.getenv("RECOMMENDED_TRADE_AMOUNT_PERCENT", "1.75"))

# Стоимость подписки на 1 месяц (USD)
SUBSCRIPTION_PRICE_USD = int(os.getenv("SUBSCRIPTION_PRICE_USD", "79"))
