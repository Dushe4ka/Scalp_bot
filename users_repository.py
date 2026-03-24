"""
Асинхронный репозиторий для коллекции users (Motor).
Структура документа и методы изменения каждого поля с обработкой ошибок.
"""

from datetime import datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import errors as pymongo_errors
from pymongo.results import UpdateResult

from config import MONGO_URI, MONGO_DB
from logger_config import setup_logger

logger = setup_logger(__name__)


# --- Исключения ---

class UsersRepositoryError(Exception):
    """Базовое исключение репозитория users."""
    pass


class UserNotFoundError(UsersRepositoryError):
    """Пользователь не найден."""
    pass


class ValidationError(UsersRepositoryError):
    """Ошибка валидации данных."""
    pass


# --- Дефолтная структура документа ---

def _default_document(tg_id: int, name: str, language: str = "ru") -> dict[str, Any]:
    return {
        "name": name,
        "tg_id": tg_id,
        "language": language,
        "subscription_data": {
            "subscription": False,
            "wait_sub_confirmation": False,
            "current_amount": 0,
            "subscription_type": "",
            "payment_date": None,
            "end_subscription_date": None,
            "total_amount": 0,
        },
        "bybit_data": {
            "sum_for_trades": 0,
            "api_key": "",
            "api_secret": "",
            "create_date": None,
            "update_date": None,
            "open_trades": 0,
        },
        "statistics": {
            "total_trades": 0,
            "total_pnl": 0.0,
            "positive_trades": 0,
            "sum_positive_trades": 0.0,
            "negative_trades": 0,
            "sum_negative_trades": 0.0,
        },
    }


class UsersRepository:
    """
    Асинхронная работа с коллекцией users через Motor.
    У каждого поля есть метод обновления с обработкой ошибок.
    """

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(MONGO_URI)
        self._db = self._client[MONGO_DB]
        self._collection: AsyncIOMotorCollection = self._db["users"]

    async def ensure_indexes(self) -> None:
        """Создать уникальный индекс по tg_id (рекомендуется вызвать при старте приложения)."""
        logger.info("Создание индекса tg_id для коллекции users")
        try:
            await self._collection.create_index("tg_id", unique=True)
            logger.info("Индекс tg_id для коллекции users успешно создан")
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при создании индекса users: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при создании индекса: {e}") from e

    # --- Базовые операции ---

    async def get_user(self, tg_id: int) -> dict[str, Any] | None:
        """Получить пользователя по tg_id."""
        logger.info("Получение пользователя tg_id=%s", tg_id)
        try:
            doc = await self._collection.find_one({"tg_id": tg_id})
            if doc is None:
                logger.info("Пользователь tg_id=%s не найден", tg_id)
            return doc
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении пользователя tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении пользователя: {e}") from e

    async def get_user_by_username_or_id(self, username_or_id: str | int) -> dict[str, Any] | None:
        """Получить пользователя по username или id."""
        logger.info("Получение пользователя по username или tg_id -- %s", username_or_id)
        try:
            doc = await self._collection.find_one({"$or": [{"username": username_or_id}, {"tg_id": username_or_id}]})
            if doc is None:
                logger.info("Пользователь %s не найден", username_or_id)
            return doc
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении пользователя username или id=%s: %s", username_or_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении пользователя: {e}") from e

    async def create_user(self, tg_id: int, name: str, language: str = None) -> dict[str, Any]:
        """Создать пользователя с дефолтной структурой. При существующем tg_id — UserNotFoundError не поднимаем, а дубликат обработаем."""
        logger.info("Создание пользователя tg_id=%s, name=%s, language=%s", tg_id, name, language)
        doc = _default_document(tg_id=tg_id, name=name, language=language)
        try:
            await self._collection.insert_one(doc)
            logger.info("Пользователь tg_id=%s успешно создан", tg_id)
            return doc
        except pymongo_errors.DuplicateKeyError:
            logger.warning("Попытка создать дубликат пользователя tg_id=%s", tg_id)
            raise UsersRepositoryError(f"Пользователь с tg_id={tg_id} уже существует") from None
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при создании пользователя tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при создании пользователя: {e}") from e

    async def get_or_create_user(self, tg_id: int, name: str, language: str = "ru") -> dict[str, Any]:
        """Получить пользователя или создать с дефолтами."""
        logger.info("get_or_create_user tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            return user
        try:
            return await self.create_user(tg_id=tg_id, name=name, language=language)
        except UsersRepositoryError as e:
            if "уже существует" in str(e):
                logger.info("Пользователь tg_id=%s появился после race, повторное чтение", tg_id)
                user = await self.get_user(tg_id)
                if user is not None:
                    return user
            raise

    async def is_subscriber(self, tg_id: int) -> bool:
        user = await self.get_user(tg_id)
        if user is not None:
            return user["subscription_data"]["subscription"]
        return False

    def _ensure_user_exists(self, result: UpdateResult, tg_id: int) -> None:
        if result.matched_count == 0:
            logger.warning("Пользователь tg_id=%s не найден при обновлении", tg_id)
            raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")

    # --- Верхний уровень: name, tg_id, language ---

    async def update_name(self, tg_id: int, name: str) -> None:
        if not name or not isinstance(name, str):
            logger.warning("update_name: невалидное значение name для tg_id=%s", tg_id)
            raise ValidationError("name должен быть непустой строкой")
        logger.info("Обновление name для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"name": name}},
            )
            self._ensure_user_exists(r, tg_id)
            logger.info("name обновлён для tg_id=%s", tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении name tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении name: {e}") from e

    async def update_tg_id(self, old_tg_id: int, new_tg_id: int) -> None:
        if not isinstance(new_tg_id, int):
            logger.warning("update_tg_id: невалидный new_tg_id для old_tg_id=%s", old_tg_id)
            raise ValidationError("tg_id должен быть int")
        logger.info("Обновление tg_id %s -> %s", old_tg_id, new_tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": old_tg_id},
                {"$set": {"tg_id": new_tg_id}},
            )
            self._ensure_user_exists(r, old_tg_id)
            logger.info("tg_id обновлён %s -> %s", old_tg_id, new_tg_id)
        except pymongo_errors.DuplicateKeyError:
            logger.warning("update_tg_id: дубликат tg_id=%s", new_tg_id)
            raise UsersRepositoryError(f"Пользователь с tg_id={new_tg_id} уже существует") from None
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении tg_id old=%s: %s", old_tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении tg_id: {e}") from e

    async def update_language(self, tg_id: int, language: str) -> None:
        if not language or not isinstance(language, str):
            logger.warning("update_language: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("language должен быть непустой строкой")
        logger.info("Обновление language для tg_id=%s -> %s", tg_id, language)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"language": language}},
            )
            self._ensure_user_exists(r, tg_id)
            logger.info("language обновлён для tg_id=%s", tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении language tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении language: {e}") from e

    # --- subscription_data ---

    async def update_subscription(self, tg_id: int, subscription: bool) -> None:
        if not isinstance(subscription, bool):
            logger.warning("update_subscription: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("subscription должен быть bool")
        logger.info("Обновление subscription для tg_id=%s -> %s", tg_id, subscription)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.subscription": subscription}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении subscription tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении subscription: {e}") from e

    async def update_wait_sub_confirmation(self, tg_id: int, wait_sub_confirmation: bool) -> None:
        if not isinstance(wait_sub_confirmation, bool):
            logger.warning("update_wait_sub_confirmation: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("wait_sub_confirmation должен быть bool")
        logger.info("Обновление wait_sub_confirmation для tg_id=%s -> %s", tg_id, wait_sub_confirmation)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.wait_sub_confirmation": wait_sub_confirmation}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении wait_sub_confirmation tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении wait_sub_confirmation: {e}") from e

    async def update_current_amount(self, tg_id: int, current_amount: int) -> None:
        if not isinstance(current_amount, int):
            logger.warning("update_current_amount: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("current_amount должен быть int")
        logger.info("Обновление current_amount для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.current_amount": int(current_amount)}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении current_amount tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении current_amount: {e}") from e

    async def update_subscription_type(self, tg_id: int, subscription_type: str) -> None:
        if not isinstance(subscription_type, str):
            logger.warning("update_subscription_type: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("subscription_type должен быть str")
        logger.info("Обновление subscription_type для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.subscription_type": subscription_type}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении subscription_type tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении subscription_type: {e}") from e

    async def update_payment_date(self, tg_id: int, payment_date: datetime | None) -> None:
        if payment_date is not None and not isinstance(payment_date, datetime):
            logger.warning("update_payment_date: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("payment_date должен быть datetime или None")
        logger.info("Обновление payment_date для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.payment_date": payment_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении payment_date tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении payment_date: {e}") from e

    async def update_end_subscription_date(self, tg_id: int, end_subscription_date: datetime | None) -> None:
        if end_subscription_date is not None and not isinstance(end_subscription_date, datetime):
            logger.warning("update_end_subscription_date: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("end_subscription_date должен быть datetime или None")
        logger.info("Обновление end_subscription_date для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.end_subscription_date": end_subscription_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении end_subscription_date tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении end_subscription_date: {e}") from e

    async def update_total_amount(self, tg_id: int, total_amount: int) -> None:
        if not isinstance(total_amount, int):
            logger.warning("update_total_amount: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("total_amount должен быть int")
        logger.info("Обновление total_amount для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.total_amount": int(total_amount)}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении total_amount tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении total_amount: {e}") from e

    async def get_total_amount(self, tg_id: int) -> int:
        user = await self.get_user(tg_id)
        if user is not None:
            raw_total = user["subscription_data"]["total_amount"]
            try:
                return int(raw_total or 0)
            except (TypeError, ValueError):
                logger.warning("get_total_amount: невалидное значение total_amount для tg_id=%s, используем 0", tg_id)
                return 0
        return 0

    # --- bybit_data ---

    async def update_sum_for_trades(self, tg_id: int, sum_for_trades: str) -> None:
        if not isinstance(sum_for_trades, str):
            logger.warning("update_sum_for_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("sum_for_trades должен быть str")
        logger.info("Обновление sum_for_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.sum_for_trades": sum_for_trades}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении sum_for_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении sum_for_trades: {e}") from e

    async def update_api_key(self, tg_id: int, api_key: str) -> None:
        if not isinstance(api_key, str):
            logger.warning("update_api_key: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("api_key должен быть str")
        logger.info("Обновление api_key для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.api_key": api_key, "bybit_data.update_date": datetime.utcnow()}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении api_key tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении api_key: {e}") from e

    async def update_api_secret(self, tg_id: int, api_secret: str) -> None:
        if not isinstance(api_secret, str):
            logger.warning("update_api_secret: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("api_secret должен быть str")
        logger.info("Обновление api_secret для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.api_secret": api_secret, "bybit_data.update_date": datetime.utcnow()}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении api_secret tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении api_secret: {e}") from e

    async def update_bybit_create_date(self, tg_id: int, create_date: datetime | None) -> None:
        if create_date is not None and not isinstance(create_date, datetime):
            logger.warning("update_bybit_create_date: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("create_date должен быть datetime или None")
        logger.info("Обновление bybit create_date для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.create_date": create_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении create_date tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении create_date: {e}") from e

    async def update_bybit_update_date(self, tg_id: int, update_date: datetime | None) -> None:
        if update_date is not None and not isinstance(update_date, datetime):
            logger.warning("update_bybit_update_date: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("update_date должен быть datetime или None")
        logger.info("Обновление bybit update_date для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.update_date": update_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении update_date tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении update_date: {e}") from e

    # --- statistics ---

    async def update_total_trades(self, tg_id: int, total_trades: int) -> None:
        if not isinstance(total_trades, (int, float)) or total_trades < 0:
            logger.warning("update_total_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("total_trades должен быть неотрицательным числом")
        logger.info("Обновление total_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.total_trades": int(total_trades)}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении total_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении total_trades: {e}") from e

    async def update_total_pnl(self, tg_id: int, total_pnl: str) -> None:
        if not isinstance(total_pnl, str):
            logger.warning("update_total_pnl: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("total_pnl должен быть str")
        logger.info("Обновление total_pnl для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.total_pnl": total_pnl}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении total_pnl tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении total_pnl: {e}") from e

    async def update_positive_trades(self, tg_id: int, positive_trades: int) -> None:
        if not isinstance(positive_trades, (int, float)) or positive_trades < 0:
            logger.warning("update_positive_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("positive_trades должен быть неотрицательным числом")
        logger.info("Обновление positive_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.positive_trades": int(positive_trades)}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении positive_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении positive_trades: {e}") from e

    async def update_sum_positive_trades(self, tg_id: int, sum_positive_trades: str) -> None:
        if not isinstance(sum_positive_trades, str):
            logger.warning("update_sum_positive_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("sum_positive_trades должен быть str")
        logger.info("Обновление sum_positive_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.sum_positive_trades": sum_positive_trades}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении sum_positive_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении sum_positive_trades: {e}") from e

    async def update_negative_trades(self, tg_id: int, negative_trades: int) -> None:
        if not isinstance(negative_trades, (int, float)) or negative_trades < 0:
            logger.warning("update_negative_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("negative_trades должен быть неотрицательным числом")
        logger.info("Обновление negative_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.negative_trades": int(negative_trades)}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении negative_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении negative_trades: {e}") from e

    async def update_sum_negative_trades(self, tg_id: int, sum_negative_trades: str) -> None:
        if not isinstance(sum_negative_trades, str):
            logger.warning("update_sum_negative_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("sum_negative_trades должен быть str")
        logger.info("Обновление sum_negative_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.sum_negative_trades": sum_negative_trades}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении sum_negative_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении sum_negative_trades: {e}") from e

    # --- Готовые функции ---

    async def user_buy_subscription_30_days(self, tg_id: int) -> None:
        
        # Храним даты как datetime, чтобы пройти валидацию update_*_date
        data_now = datetime.now()
        data_end = data_now + timedelta(days=30)

        total_amount = await self.get_total_amount(tg_id)

        await self.update_wait_sub_confirmation(tg_id, True)
        await self.update_subscription_type(tg_id, "30 дней")
        await self.update_payment_date(tg_id, data_now)
        await self.update_end_subscription_date(tg_id, data_end)
        await self.update_current_amount(tg_id, 99)
        await self.update_total_amount(tg_id, total_amount + 99)

        logger.info(f"Данные пользователя {tg_id} обновлены (покупка подписки 30 дней)")

    async def admin_check_subscription(self, tg_id: int) -> None:

        await self.update_wait_sub_confirmation(tg_id, False)
        await self.update_subscription(tg_id, True)

        logger.info(f"Данные пользователя {tg_id} обновлены (подтверждение подписки)")

    async def close(self) -> None:
        """Закрыть соединение с MongoDB."""
        logger.info("Закрытие соединения с MongoDB (users)")
        self._client.close()

db = UsersRepository()