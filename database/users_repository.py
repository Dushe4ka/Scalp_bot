"""
Асинхронный репозиторий для коллекции users (Motor).
Структура документа и методы изменения каждого поля с обработкой ошибок.
"""

from datetime import datetime, timedelta
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection
from pymongo import errors as pymongo_errors
from pymongo.results import UpdateResult

from config import MONGO_URI, MONGO_DB, SUBSCRIPTION_PRICE_USD
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
        "language_selected": False,
        "subscription_data": {
            "subscription": False,
            "wait_sub_confirmation": False,
            "trial_used": False,
            "current_amount": 0,
            "subscription_type": "",
            "payment_date": None,
            "end_subscription_date": None,
            "notify_3d_for_end": None,
            "notify_1d_for_end": None,
            "notify_expired_for_end": None,
            "total_amount": 0,
            "previous_payment_date": None,
            "previous_subscription_type": "",
            "previous_end_subscription_date": None,
        },
        "bybit_data": {
            "sum_for_trades": 0,
            "api_key": "",
            "api_secret": "",
            "create_date": None,
            "update_date": None,
            "api_key_expired_at": None,
            "notify_api_key_3d": None,
            "notify_api_key_1d": None,
            "notify_api_key_expired": None,
            "max_concurrent_trades": 1,
            "api_key_instruction_shown": False,
            "open_trades": 0,
            "stop_trading": False,
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
        """
        Получить пользователя по username или id.
        return:
        Возвращаем все кроме _id: ObjectID
        """

        logger.info("Получение пользователя по username или tg_id -- %s", username_or_id)
        try:
            or_clauses: list[dict[str, Any]] = [{"name": username_or_id}]

            # tg_id в БД хранится как int, поэтому если вводим цифры строкой — конвертируем.
            if isinstance(username_or_id, str) and username_or_id.isdigit():
                or_clauses.append({"tg_id": int(username_or_id)})
            elif not isinstance(username_or_id, str):
                or_clauses.append({"tg_id": username_or_id})

            doc = await self._collection.find_one({"$or": or_clauses})
            if doc is None:
                logger.info("Пользователь %s не найден", username_or_id)
                return None

            return {k: v for k, v in doc.items() if k != "_id"}
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении пользователя username или id=%s: %s", username_or_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении пользователя: {e}") from e

    async def count_users_waiting_confirmation(self) -> int:
        """Число пользователей с wait_sub_confirmation == True."""
        logger.info("Подсчёт пользователей, ожидающих подтверждения подписки")
        try:
            n = await self._collection.count_documents({"subscription_data.wait_sub_confirmation": True})
            return int(n)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка count_users_waiting_confirmation: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при подсчёте: {e}") from e

    async def list_users_waiting_confirmation(self, skip: int, limit: int) -> list[dict[str, Any]]:
        """Список пользователей с wait_sub_confirmation == True (сортировка по tg_id)."""
        if skip < 0 or limit < 1:
            raise ValidationError("skip и limit должны быть валидными")
        logger.info("Список ожидающих подтверждения: skip=%s limit=%s", skip, limit)
        try:
            cursor = (
                self._collection.find(
                    {"subscription_data.wait_sub_confirmation": True},
                    {"_id": 0, "name": 1, "tg_id": 1},
                )
                .sort("tg_id", 1)
                .skip(skip)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка list_users_waiting_confirmation: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении списка: {e}") from e

    async def count_subscribers(self) -> int:
        """Число пользователей с активной подпиской (subscription == True)."""
        logger.info("Подсчёт подписчиков")
        try:
            n = await self._collection.count_documents({"subscription_data.subscription": True})
            return int(n)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка count_subscribers: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при подсчёте: {e}") from e

    async def list_subscribers(self, skip: int, limit: int) -> list[dict[str, Any]]:
        """Список подписчиков (сортировка по tg_id)."""
        if skip < 0 or limit < 1:
            raise ValidationError("skip и limit должны быть валидными")
        logger.info("Список подписчиков: skip=%s limit=%s", skip, limit)
        try:
            cursor = (
                self._collection.find(
                    {"subscription_data.subscription": True},
                    {"_id": 0, "name": 1, "tg_id": 1},
                )
                .sort("tg_id", 1)
                .skip(skip)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка list_subscribers: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении списка: {e}") from e

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

    async def is_wait_sub_confirmation(self, tg_id: int) -> bool:
        user = await self.get_user(tg_id)
        if user is not None:
            return user["subscription_data"]["wait_sub_confirmation"]
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
                {"$set": {"language": language, "language_selected": True}},
            )
            self._ensure_user_exists(r, tg_id)
            logger.info("language обновлён для tg_id=%s", tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении language tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении language: {e}") from e

    # --- subscription_data ---
    async def get_subscription_type(self, tg_id: int) -> str:
        """Получить тип подписки для пользователя"""
        logger.info("Получение типа подписки для пользователя tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            return user["subscription_data"]["subscription_type"]
        logger.info("Пользователь tg_id=%s не найден", tg_id)
        raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")

    async def get_end_subscription_date(self, tg_id: int) -> datetime:
        """Получить дату окончания подписки для пользователя"""
        logger.info("Получение даты окончания подписки для пользователя tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            return user["subscription_data"]["end_subscription_date"]
        logger.info("Пользователь tg_id=%s не найден", tg_id)
        raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")

    async def get_trial_used(self, tg_id: int) -> bool:
        """
        Использовал ли пользователь бесплатный пробный период.
        Старые документы без поля trial_used трактуются как 'не использован'.
        """
        user = await self.get_user(tg_id)
        if user is not None:
            return bool((user.get("subscription_data") or {}).get("trial_used"))
        return False

    async def start_trial_period(self, tg_id: int) -> bool:
        """
        Выдаёт бесплатный пробный период на 7 дней. Атомарно (условие trial_used != True —
        в фильтре запроса, не read-then-write) — защита от гонки при двойном тапе/повторном
        вызове. Возвращает False, если триал уже был использован (или пользователь не найден).
        """
        logger.info("Запрос на выдачу пробного периода tg_id=%s", tg_id)
        now = datetime.now()
        end_date = now + timedelta(days=7)
        try:
            r = await self._collection.update_one(
                {
                    "tg_id": tg_id,
                    "subscription_data.trial_used": {"$ne": True},
                    "subscription_data.subscription": {"$ne": True},
                },
                {
                    "$set": {
                        "subscription_data.subscription": True,
                        "subscription_data.subscription_type": "trial",
                        "subscription_data.trial_used": True,
                        "subscription_data.payment_date": now,
                        "subscription_data.end_subscription_date": end_date,
                        "subscription_data.wait_sub_confirmation": False,
                    }
                },
            )
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка start_trial_period tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при выдаче пробного периода: {e}") from e

        granted = r.matched_count == 1
        if granted:
            logger.info("Пробный период выдан tg_id=%s, до %s", tg_id, end_date)
        else:
            logger.info("Пробный период НЕ выдан tg_id=%s (уже использован или не найден)", tg_id)
        return granted

    async def admin_reset_trial_used(self, tg_id: int) -> None:
        """Сбрасывает флаг использования триала (повторный триал по решению админа/техподдержки)."""
        logger.info("Сброс флага использования триала tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.trial_used": False}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка admin_reset_trial_used tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при сбросе флага триала: {e}") from e

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

    async def get_subscription_status(self, tg_id: int) -> bool:
        """Получить состояние подписки для пользователя"""
        logger.info("Получение состояния подписки для пользователя tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            return user["subscription_data"]["subscription"]
        logger.info("Пользователь tg_id=%s не найден", tg_id)
        raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")

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

    async def update_end_subscription_date_from_string(self, tg_id: int, date_str: str) -> datetime:
        """
        Обновить дату окончания подписки из строки формата `yyyy.mm.dd. hh.mm.ss`.
        В Mongo дата будет сохранена как BSON Date (ISO date).
        """
        if not isinstance(date_str, str) or not date_str.strip():
            logger.warning("update_end_subscription_date_from_string: пустая дата для tg_id=%s", tg_id)
            raise ValidationError("Дата должна быть непустой строкой")

        normalized_date = date_str.strip()
        try:
            parsed_date = datetime.strptime(normalized_date, "%Y.%m.%d. %H.%M.%S")
        except ValueError as e:
            logger.warning(
                "update_end_subscription_date_from_string: неверный формат даты для tg_id=%s, value=%s",
                tg_id,
                normalized_date,
            )
            raise ValidationError("Неверный формат даты. Используйте yyyy.mm.dd. hh.mm.ss") from e

        await self.update_end_subscription_date(tg_id, parsed_date)
        logger.info("Дата окончания подписки обновлена из строки для tg_id=%s", tg_id)
        return parsed_date

    async def prolong_end_subscription_date(self, tg_id: int, end_subscription_date: datetime | None, subscription_type: str) -> None:
        if subscription_type == "1 мес":
            end_subscription_date = end_subscription_date + timedelta(days=30)
        elif subscription_type == "3 мес":
            end_subscription_date = end_subscription_date + timedelta(days=90)
        elif subscription_type == "6 мес":
            end_subscription_date = end_subscription_date + timedelta(days=180)
        elif subscription_type == "1 год":
            end_subscription_date = end_subscription_date + timedelta(days=365)
        else:
            logger.warning("prolong_end_subscription_date: неизвестный тип подписки для tg_id=%s", tg_id)
            raise ValidationError("Неизвестный тип подписки")
        await self.update_end_subscription_date(tg_id, end_subscription_date)

    async def update_end_subscription_date_by_type(self, tg_id: int, subscription_type: str) -> None:
        if not isinstance(subscription_type, str):
            logger.warning("update_end_subscription_date_by_type: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("subscription_type должен быть str")
        logger.info("Обновление end_subscription_date для tg_id=%s -> %s", tg_id, subscription_type)

        data_now = datetime.now()

        if subscription_type == "1 мес":
            data_end = data_now + timedelta(days=30)
        elif subscription_type == "3 мес":
            data_end = data_now + timedelta(days=90)
        elif subscription_type == "6 мес":
            data_end = data_now + timedelta(days=180)
        elif subscription_type == "1 год":
            data_end = data_now + timedelta(days=365)
        else:
            logger.warning("update_end_subscription_date_by_type: неизвестный тип подписки для tg_id=%s", tg_id)
            raise ValidationError("Неизвестный тип подписки")

        end_subscription_date = data_end

        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.end_subscription_date": end_subscription_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении end_subscription_date_by_type tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении end_subscription_date_by_type: {e}") from e

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

    async def update_previous_data(self, tg_id: int) -> None:
        """Обновление предыдущих данных для пользователя"""
        logger.info("Обновление предыдущих данных для пользователя tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            previous_payment_date = user["subscription_data"]["payment_date"]
            previous_subscription_type = user["subscription_data"]["subscription_type"]
            previous_end_subscription_date = user["subscription_data"]["end_subscription_date"]
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"subscription_data.previous_payment_date": previous_payment_date, "subscription_data.previous_subscription_type": previous_subscription_type, "subscription_data.previous_end_subscription_date": previous_end_subscription_date}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении предыдущих данных tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении предыдущих данных: {e}") from e
    
    async def cancel_previous_data(self, tg_id: int) -> None:
        """
        Возврат предыдущих данных на место нынешних у пользователя и очистка предыдущих данных
        Проверка чтобы старые данные не были None, иначе не будет обновления
        """
        logger.info("Возврат предыдущих данных на место нынешних у пользователя tg_id=%s", tg_id)
        user = await self.get_user(tg_id)
        if user is not None:
            previous_payment_date = user["subscription_data"]["previous_payment_date"]
            previous_subscription_type = user["subscription_data"]["previous_subscription_type"]
            previous_end_subscription_date = user["subscription_data"]["previous_end_subscription_date"]
            if previous_payment_date is not None and previous_subscription_type is not None and previous_end_subscription_date is not None:
                await self.update_payment_date(tg_id, previous_payment_date)
                await self.update_subscription_type(tg_id, previous_subscription_type)
                await self.update_end_subscription_date(tg_id, previous_end_subscription_date)
                logger.info("Предыдущие данные для пользователя tg_id=%s возвращены на место нынешних", tg_id)

                try:
                    r = await self._collection.update_one(
                        {"tg_id": tg_id},
                        {"$set": {"subscription_data.previous_payment_date": None, "subscription_data.previous_subscription_type": None, "subscription_data.previous_end_subscription_date": None}},
                    )
                    self._ensure_user_exists(r, tg_id)
                except pymongo_errors.PyMongoError as e:
                    logger.error("Ошибка при очистке предыдущих данных tg_id=%s: %s", tg_id, e, exc_info=True)
                    raise UsersRepositoryError(f"Ошибка при очистке предыдущих данных: {e}") from e
            else:
                logger.info("Предыдущие данные для пользователя tg_id=%s не найдены, не будет обновления", tg_id)
  
    # --- bybit_data ---

    @staticmethod
    def _bybit_create_date_fields_if_first_full_pair(
        existing_create_date: Any,
        new_api_key: str,
        new_api_secret: str,
        utc_now: datetime,
    ) -> dict[str, datetime]:
        """
        Ставит create_date при первой полной паре ключ+секрет (оба непустые после strip),
        только если в документе create_date ещё не задан.
        """
        if existing_create_date is not None:
            return {}
        key_ok = isinstance(new_api_key, str) and bool(new_api_key.strip())
        secret_ok = isinstance(new_api_secret, str) and bool(new_api_secret.strip())
        if key_ok and secret_ok:
            return {"bybit_data.create_date": utc_now}
        return {}

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
        user = await self.get_user(tg_id)
        if user is None:
            raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")
        bybit = user.get("bybit_data") or {}
        now = datetime.utcnow()
        secret_after = bybit.get("api_secret") if isinstance(bybit.get("api_secret"), str) else ""
        create_extra = self._bybit_create_date_fields_if_first_full_pair(
            bybit.get("create_date"),
            api_key,
            secret_after,
            now,
        )
        set_fields: dict[str, Any] = {
            "bybit_data.api_key": api_key,
            "bybit_data.update_date": now,
            **create_extra,
        }
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": set_fields},
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
        user = await self.get_user(tg_id)
        if user is None:
            raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")
        bybit = user.get("bybit_data") or {}
        now = datetime.utcnow()
        key_after = bybit.get("api_key") if isinstance(bybit.get("api_key"), str) else ""
        create_extra = self._bybit_create_date_fields_if_first_full_pair(
            bybit.get("create_date"),
            key_after,
            api_secret,
            now,
        )
        set_fields: dict[str, Any] = {
            "bybit_data.api_secret": api_secret,
            "bybit_data.update_date": now,
            **create_extra,
        }
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": set_fields},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении api_secret tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении api_secret: {e}") from e

    async def sync_api_key_expired_at(self, tg_id: int, expired_at: datetime | None) -> None:
        """Обновляет дату истечения API-ключа, если она изменилась; сбрасывает отметки уведомлений."""
        user = await self.get_user(tg_id)
        if user is None:
            raise UserNotFoundError(f"Пользователь с tg_id={tg_id} не найден")

        bybit = user.get("bybit_data") or {}
        stored = bybit.get("api_key_expired_at")

        if stored is None and expired_at is None:
            return

        if isinstance(stored, datetime) and isinstance(expired_at, datetime):
            a = stored.replace(tzinfo=None) if stored.tzinfo else stored
            b = expired_at.replace(tzinfo=None) if expired_at.tzinfo else expired_at
            if abs((a - b).total_seconds()) < 120:
                return

        set_fields: dict[str, Any] = {
            "bybit_data.api_key_expired_at": expired_at,
            "bybit_data.notify_api_key_3d": None,
            "bybit_data.notify_api_key_1d": None,
            "bybit_data.notify_api_key_expired": None,
        }
        logger.info("Обновление api_key_expired_at для tg_id=%s -> %s", tg_id, expired_at)
        try:
            r = await self._collection.update_one({"tg_id": tg_id}, {"$set": set_fields})
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка sync_api_key_expired_at tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении api_key_expired_at: {e}") from e

    async def mark_api_key_instruction_shown(self, tg_id: int) -> None:
        logger.info("Отметка api_key_instruction_shown для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.api_key_instruction_shown": True}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка mark_api_key_instruction_shown tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка mark_api_key_instruction_shown: {e}") from e

    async def get_max_concurrent_trades(self, tg_id: int) -> int:
        user = await self.get_user(tg_id)
        if user is None:
            return 1
        bybit = user.get("bybit_data") or {}
        try:
            value = int(bybit.get("max_concurrent_trades") or 1)
        except (TypeError, ValueError):
            value = 1
        return max(1, value)

    async def migrate_max_concurrent_trades_default(self) -> dict[str, int]:
        """Проставляет max_concurrent_trades=1 пользователям без поля."""
        try:
            result = await self._collection.update_many(
                {"bybit_data.max_concurrent_trades": {"$exists": False}},
                {"$set": {"bybit_data.max_concurrent_trades": 1}},
            )
            return {
                "matched": int(result.matched_count),
                "modified": int(result.modified_count),
            }
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка migrate_max_concurrent_trades_default: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка миграции max_concurrent_trades: {e}") from e

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

    async def update_stop_trading(self, tg_id: int, stop_trading: bool) -> None:
        if not isinstance(stop_trading, bool):
            logger.warning("update_stop_trading: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("stop_trading должен быть bool")
        logger.info("Обновление stop_trading для tg_id=%s -> %s", tg_id, stop_trading)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"bybit_data.stop_trading": stop_trading}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении stop_trading tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении stop_trading: {e}") from e


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

    async def update_sum_positive_trades(self, tg_id: int, sum_positive_trades: float | str | int) -> None:
        try:
            value = float(sum_positive_trades)
        except (TypeError, ValueError):
            logger.warning("update_sum_positive_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("sum_positive_trades должен быть числом")
        if value < 0:
            raise ValidationError("sum_positive_trades не может быть отрицательным")
        logger.info("Обновление sum_positive_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.sum_positive_trades": value}},
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

    async def update_sum_negative_trades(self, tg_id: int, sum_negative_trades: float | str | int) -> None:
        try:
            value = float(sum_negative_trades)
        except (TypeError, ValueError):
            logger.warning("update_sum_negative_trades: невалидное значение для tg_id=%s", tg_id)
            raise ValidationError("sum_negative_trades должен быть числом")
        if value < 0:
            raise ValidationError("sum_negative_trades не может быть отрицательным")
        logger.info("Обновление sum_negative_trades для tg_id=%s", tg_id)
        try:
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$set": {"statistics.sum_negative_trades": value}},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при обновлении sum_negative_trades tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при обновлении sum_negative_trades: {e}") from e

    async def list_trading_candidates(self) -> list[dict[str, Any]]:
        """
        Возвращает пользователей с активной подпиской и полями для запуска торговли.
        Фильтрация по ключам/stop_trading/sum_for_trades выполняется на уровне сервиса запуска.
        """
        logger.info("Получение кандидатов для автозапуска торговли")
        try:
            cursor = self._collection.find(
                {"subscription_data.subscription": True},
                {
                    "_id": 0,
                    "tg_id": 1,
                    "name": 1,
                    "subscription_data.subscription": 1,
                    "bybit_data.api_key": 1,
                    "bybit_data.api_secret": 1,
                    "bybit_data.stop_trading": 1,
                    "bybit_data.sum_for_trades": 1,
                    "bybit_data.max_concurrent_trades": 1,
                },
            ).sort("tg_id", 1)
            return await cursor.to_list(length=None)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка list_trading_candidates: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка получения кандидатов торговли: {e}") from e

    async def apply_trade_statistics_delta(self, tg_id: int, pnl_usdt: float) -> None:
        """
        Обновляет агрегированную статистику пользователя после завершения сделки.
        """
        if not isinstance(pnl_usdt, (int, float)):
            raise ValidationError("pnl_usdt должен быть числом")

        inc_fields: dict[str, Any] = {
            "statistics.total_trades": 1,
            "statistics.total_pnl": float(pnl_usdt),
        }
        if pnl_usdt > 0:
            inc_fields["statistics.positive_trades"] = 1
            inc_fields["statistics.sum_positive_trades"] = float(pnl_usdt)
        elif pnl_usdt < 0:
            inc_fields["statistics.negative_trades"] = 1
            inc_fields["statistics.sum_negative_trades"] = abs(float(pnl_usdt))

        logger.info("Применение дельты статистики для tg_id=%s, pnl_usdt=%s", tg_id, pnl_usdt)
        try:
            user = await self._collection.find_one({"tg_id": tg_id}, {"statistics": 1})
            if user:
                from database.user_statistics_coercion import statistics_coerce_update

                sets = statistics_coerce_update(user.get("statistics"))
                if sets:
                    await self._collection.update_one({"tg_id": tg_id}, {"$set": sets})
            r = await self._collection.update_one(
                {"tg_id": tg_id},
                {"$inc": inc_fields},
            )
            self._ensure_user_exists(r, tg_id)
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка apply_trade_statistics_delta tg_id=%s: %s", tg_id, e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка обновления статистики сделки: {e}") from e

    # --- Готовые функции ---

    async def user_buy_subscription_30_days(self, tg_id: int) -> None:
        """Покупка подписки 30 дней для пользователя или продление подписки на 30 дней"""
        # Сохраняем текущие данные как прошлые и обновляем текущие
        if await self.is_subscriber(tg_id):
            await self.update_previous_data(tg_id)
        
        # Храним даты как datetime, чтобы пройти валидацию update_*_date
        data_now = datetime.now()

        total_amount = await self.get_total_amount(tg_id)

        await self.update_wait_sub_confirmation(tg_id, True)
        await self.update_subscription_type(tg_id, "1 мес")
        await self.update_payment_date(tg_id, data_now)
        await self.update_current_amount(tg_id, SUBSCRIPTION_PRICE_USD)
        await self.update_total_amount(tg_id, total_amount + SUBSCRIPTION_PRICE_USD)

        logger.info(f"Данные пользователя {tg_id} обновлены (покупка подписки 30 дней)")

    async def admin_check_subscription(self, tg_id: int) -> None:
        
        user_subscription_type = await self.get_subscription_type(tg_id)
        await self.update_end_subscription_date_by_type(tg_id, user_subscription_type)
        await self.update_wait_sub_confirmation(tg_id, False)
        await self.update_subscription(tg_id, True)

        logger.info(f"Данные пользователя {tg_id} обновлены (подтверждение подписки и дата окончания подписки)")

    async def admin_cancel_subscription(self, tg_id: int) -> None:
        await self.update_subscription(tg_id, False)
        await self.update_wait_sub_confirmation(tg_id, False)
        await self.update_end_subscription_date(tg_id, None)
        await self.update_subscription_type(tg_id, "")
        await self.update_payment_date(tg_id, None)
        await self.update_current_amount(tg_id, 0)
        await self.update_total_amount(tg_id, 0)

        logger.info(f"Данные пользователя {tg_id} обновлены (Не подтверждена подписка)")

    async def admin_prolong_subscription(self, tg_id: int) -> None:
        """Админ продлевает подписку пользователю, по типу подписки"""
        user_subscription_type = await self.get_subscription_type(tg_id)
        date_end_subscription = await self.get_end_subscription_date(tg_id)
        await self.update_wait_sub_confirmation(tg_id, False)
        await self.prolong_end_subscription_date(tg_id, date_end_subscription, user_subscription_type)

        logger.info(f"Админ продлил подписку для пользователя {tg_id}")

    async def admin_cancel_prolong_subscription(self, tg_id: int) -> None:
        """Админ отклоняет продление подписки пользователя"""
        await self.cancel_previous_data(tg_id)
        await self.update_wait_sub_confirmation(tg_id, False)

        logger.info(f"Админ отклонил продление подписки {tg_id}")

    async def get_count_subscribers(self) -> int:
        """
        Возвращает количество подписчиков (subscription_data.subscription: true)
        """
        try:
            r = await self._collection.count_documents({"subscription_data.subscription": True})
            return r
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении количества подписчиков: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении количества подписчиков: {e}") from e

    async def get_count_users_waiting_confirmation(self) -> int:
        """
        Возвращает количество пользователей, ожидающих подтверждения подписки (subscription_data.wait_sub_confirmation: true)
        """
        try:
            r = await self._collection.count_documents({"subscription_data.wait_sub_confirmation": True})
            return r
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении количества пользователей, ожидающих подтверждения подписки: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении количества пользователей, ожидающих подтверждения подписки: {e}") from e

    async def get_count_all_users(self) -> int:
        """
        Возвращает количество всех пользователей (countDocuments)
        """
        try:
            r = await self._collection.count_documents({})
            return r
        except pymongo_errors.PyMongoError as e:
            logger.error("Ошибка при получении количества всех пользователей: %s", e, exc_info=True)
            raise UsersRepositoryError(f"Ошибка при получении количества всех пользователей: {e}") from e

    async def close(self) -> None:
        """Закрыть соединение с MongoDB."""
        logger.info("Закрытие соединения с MongoDB (users)")
        self._client.close()

db = UsersRepository()