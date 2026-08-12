# Бесплатный пробный период — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать любому пользователю self-service бесплатный 7-дневный пробный период с полным доступом
(как при подписке), ровно один раз, без поломки существующей логики подписки/торговли.

**Architecture:** Триал живёт внутри уже существующего `subscription_data` (без новой коллекции):
`subscription_type = "trial"` + новый флаг `trial_used`. Гейт торговли
(`list_trading_candidates`) и Celery Beat проверка (`run_subscription_lifecycle_check`) фильтруют
только по `subscription: True` — они уже одинаково работают для любого `subscription_type`, поэтому
не меняются вообще. Новый метод `start_trial_period()` атомарно (условие в фильтре Mongo-запроса)
выдаёт доступ и метит `trial_used=True`. Точки входа — кнопка в главном меню и кнопка в профиле без
подписки, обе за экраном-подтверждением. Уведомления о триале — отдельные тексты (не переиспользуют
`subscription_reminder_*` дословно).

**Tech Stack:** Python 3.12, Motor (async MongoDB), aiogram 3.x, `unittest` (stdlib, без pytest —
`python -m unittest`).

## Global Constraints

- Один и тот же `subscription_data`, БЕЗ отдельной коллекции/гейта для триала.
- `list_trading_candidates`, `run_subscription_lifecycle_check`, `deactivate_subscription` —
  **не менять**, они уже универсальны для любого `subscription_type`.
- Триал выдаётся **ровно один раз** — атомарная защита на уровне репозитория (условие в фильтре
  Mongo-запроса), не только скрытием кнопки в UI.
- Старые пользовательские документы без поля `trial_used` должны трактоваться как "триал не
  использован" (никакой миграции данных не требуется — `.get("trial_used")` и Mongo-оператор `$ne`
  одинаково трактуют отсутствие поля как `False`/не-`True`).
- Тексты уведомлений о триале — отдельные ключи (`trial_reminder_3d`, `trial_reminder_1d`,
  `trial_expired`), не переиспользуют `subscription_reminder_*` дословно.
- Тесты — только `unittest` (`python -m unittest tests.test_trial_period -v`), без pytest,
  без реального Mongo (Motor-коллекция мокается).

---

### Task 1: Данные и метод репозитория `start_trial_period`

**Files:**
- Modify: `database/users_repository.py`
- Create: `tests/test_trial_period.py`

**Interfaces:**
- Produces: `database.users_repository.UsersRepository.start_trial_period(tg_id: int) -> bool`,
  `database.users_repository.UsersRepository.get_trial_used(tg_id: int) -> bool`,
  `database.users_repository.UsersRepository.admin_reset_trial_used(tg_id: int) -> None`,
  новое поле `subscription_data.trial_used: bool` (default `False`) в `_default_document`

- [ ] **Step 1: Написать падающие тесты**

Создать `tests/test_trial_period.py`:

```python
"""Unit tests for the free trial period feature (mocked Motor collection, no real Mongo)."""
from __future__ import annotations

import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from database.users_repository import UsersRepository


class StartTrialPeriodTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = UsersRepository()
        self.repo._collection = MagicMock()

    async def test_grants_trial_first_time(self):
        result = MagicMock()
        result.matched_count = 1
        self.repo._collection.update_one = AsyncMock(return_value=result)

        granted = await self.repo.start_trial_period(123)

        self.assertTrue(granted)
        args, _ = self.repo._collection.update_one.call_args
        query, update = args
        self.assertEqual(query, {"tg_id": 123, "subscription_data.trial_used": {"$ne": True}})
        sets = update["$set"]
        self.assertEqual(sets["subscription_data.subscription"], True)
        self.assertEqual(sets["subscription_data.subscription_type"], "trial")
        self.assertEqual(sets["subscription_data.trial_used"], True)
        self.assertEqual(sets["subscription_data.wait_sub_confirmation"], False)
        delta = sets["subscription_data.end_subscription_date"] - sets["subscription_data.payment_date"]
        self.assertEqual(delta, timedelta(days=7))

    async def test_rejects_when_already_used(self):
        result = MagicMock()
        result.matched_count = 0
        self.repo._collection.update_one = AsyncMock(return_value=result)

        granted = await self.repo.start_trial_period(123)

        self.assertFalse(granted)


class GetTrialUsedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = UsersRepository()

    async def test_true_when_flag_set(self):
        self.repo.get_user = AsyncMock(
            return_value={"subscription_data": {"trial_used": True}}
        )
        self.assertTrue(await self.repo.get_trial_used(123))

    async def test_false_when_field_missing(self):
        """Старые документы без поля trial_used трактуются как 'не использован'."""
        self.repo.get_user = AsyncMock(return_value={"subscription_data": {}})
        self.assertFalse(await self.repo.get_trial_used(123))

    async def test_false_when_user_not_found(self):
        self.repo.get_user = AsyncMock(return_value=None)
        self.assertFalse(await self.repo.get_trial_used(123))


class AdminResetTrialUsedTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repo = UsersRepository()
        self.repo._collection = MagicMock()

    async def test_resets_flag(self):
        result = MagicMock()
        result.matched_count = 1
        self.repo._collection.update_one = AsyncMock(return_value=result)

        await self.repo.admin_reset_trial_used(123)

        args, _ = self.repo._collection.update_one.call_args
        query, update = args
        self.assertEqual(query, {"tg_id": 123})
        self.assertEqual(update, {"$set": {"subscription_data.trial_used": False}})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `python -m unittest tests.test_trial_period -v`
Expected: `FAIL` / `AttributeError` — `start_trial_period`/`get_trial_used`/`admin_reset_trial_used` ещё
не существуют на `UsersRepository`.

- [ ] **Step 3: Добавить поле в дефолтный документ**

В `database/users_repository.py`, функция `_default_document` — было:
```python
        "subscription_data": {
            "subscription": False,
            "wait_sub_confirmation": False,
            "current_amount": 0,
```
Стало (добавлена строка `"trial_used": False,` сразу после `"wait_sub_confirmation"`):
```python
        "subscription_data": {
            "subscription": False,
            "wait_sub_confirmation": False,
            "trial_used": False,
            "current_amount": 0,
```

- [ ] **Step 4: Добавить методы в `UsersRepository`**

Добавить в класс `UsersRepository` (например, сразу после `get_end_subscription_date`, рядом с
остальными методами `subscription_data`):

```python
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
                {"tg_id": tg_id, "subscription_data.trial_used": {"$ne": True}},
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
```

- [ ] **Step 5: Запустить тесты и убедиться, что они проходят**

Run: `python -m unittest tests.test_trial_period -v`
Expected: все 6 тестов (`StartTrialPeriodTests` × 2, `GetTrialUsedTests` × 3, `AdminResetTrialUsedTests` × 1) — `ok`.

- [ ] **Step 6: Commit**

```bash
git add database/users_repository.py tests/test_trial_period.py
git commit -m "feat: add start_trial_period/get_trial_used/admin_reset_trial_used to UsersRepository"
```

---

### Task 2: Отдельные тексты для напоминаний о триале в Celery Beat

**Files:**
- Modify: `celery_app/subscription_lifecycle_service.py`
- Modify: `tests/test_trial_period.py`

**Interfaces:**
- Consumes: `sub.get("subscription_type")` (уже есть в `subscription_data`, Task 1 добавляет только `trial_used`)
- Produces: `celery_app.subscription_lifecycle_service._reminder_key(subscription_type: str | None, suffix: str) -> str`

- [ ] **Step 1: Написать падающий тест**

Добавить в `tests/test_trial_period.py` (после `AdminResetTrialUsedTests`, перед `if __name__ == "__main__":`):

```python
class ReminderKeyTests(unittest.TestCase):
    def test_trial_uses_trial_keys(self):
        from celery_app.subscription_lifecycle_service import _reminder_key

        self.assertEqual(_reminder_key("trial", "reminder_3d"), "trial_reminder_3d")
        self.assertEqual(_reminder_key("trial", "reminder_1d"), "trial_reminder_1d")
        self.assertEqual(_reminder_key("trial", "expired"), "trial_expired")

    def test_non_trial_uses_subscription_keys(self):
        from celery_app.subscription_lifecycle_service import _reminder_key

        self.assertEqual(_reminder_key("1 мес", "reminder_3d"), "subscription_reminder_3d")
        self.assertEqual(_reminder_key(None, "expired"), "subscription_expired")
        self.assertEqual(_reminder_key("", "reminder_1d"), "subscription_reminder_1d")
```

- [ ] **Step 2: Запустить тест и убедиться, что он падает**

Run: `python -m unittest tests.test_trial_period.ReminderKeyTests -v`
Expected: `FAIL` / `ImportError` — `_reminder_key` ещё не существует.

- [ ] **Step 3: Добавить `_reminder_key` и переключить вызовы**

В `celery_app/subscription_lifecycle_service.py`, добавить новую функцию сразу после
`_message_for_user` (после строки `return template.format(end_date=_format_end_date(end_date))`):

```python
def _reminder_key(subscription_type: str | None, suffix: str) -> str:
    """suffix: 'reminder_3d' | 'reminder_1d' | 'expired'. trial -> trial_*, иначе subscription_*."""
    prefix = "trial" if (subscription_type or "").strip() == "trial" else "subscription"
    return f"{prefix}_{suffix}"
```

Внутри `run_subscription_lifecycle_check`, было:
```python
        language = user.get("language")
        days_left = _days_until_end(end_date, now)

        try:
            if days_left <= 0:
                if not _same_end_moment(sub.get(_NOTIFY_EXPIRED), end_date):
                    text = _message_for_user(language, "subscription_expired", end_date=end_date)
                    if _send_user_notification(tg_id, text):
                        subscription_lifecycle_db.mark_notification_sent(
                            tg_id, _NOTIFY_EXPIRED, end_date
                        )
                subscription_lifecycle_db.deactivate_subscription(tg_id)
                stats["expired"] += 1
                logger.info(
                    "Подписка отключена (истекла): tg_id=%s end=%s",
                    tg_id,
                    _format_end_date(end_date),
                )
                continue

            if days_left == 3 and not _same_end_moment(sub.get(_NOTIFY_3D), end_date):
                text = _message_for_user(language, "subscription_reminder_3d", end_date=end_date)
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_3D, end_date)
                    stats["reminder_3d"] += 1
                continue

            if days_left == 1 and not _same_end_moment(sub.get(_NOTIFY_1D), end_date):
                text = _message_for_user(language, "subscription_reminder_1d", end_date=end_date)
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_1D, end_date)
                    stats["reminder_1d"] += 1
                continue
```

Стало (единственное изменение — вычисляется `sub_type` и подставляется в `_reminder_key(...)`
вместо жёстко заданных строк `"subscription_expired"`/`"subscription_reminder_3d"`/`"subscription_reminder_1d"`):
```python
        language = user.get("language")
        sub_type = sub.get("subscription_type")
        days_left = _days_until_end(end_date, now)

        try:
            if days_left <= 0:
                if not _same_end_moment(sub.get(_NOTIFY_EXPIRED), end_date):
                    text = _message_for_user(
                        language, _reminder_key(sub_type, "expired"), end_date=end_date
                    )
                    if _send_user_notification(tg_id, text):
                        subscription_lifecycle_db.mark_notification_sent(
                            tg_id, _NOTIFY_EXPIRED, end_date
                        )
                subscription_lifecycle_db.deactivate_subscription(tg_id)
                stats["expired"] += 1
                logger.info(
                    "Подписка отключена (истекла): tg_id=%s end=%s",
                    tg_id,
                    _format_end_date(end_date),
                )
                continue

            if days_left == 3 and not _same_end_moment(sub.get(_NOTIFY_3D), end_date):
                text = _message_for_user(
                    language, _reminder_key(sub_type, "reminder_3d"), end_date=end_date
                )
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_3D, end_date)
                    stats["reminder_3d"] += 1
                continue

            if days_left == 1 and not _same_end_moment(sub.get(_NOTIFY_1D), end_date):
                text = _message_for_user(
                    language, _reminder_key(sub_type, "reminder_1d"), end_date=end_date
                )
                if _send_user_notification(tg_id, text):
                    subscription_lifecycle_db.mark_notification_sent(tg_id, _NOTIFY_1D, end_date)
                    stats["reminder_1d"] += 1
                continue
```

- [ ] **Step 4: Запустить тест и убедиться, что он проходит**

Run: `python -m unittest tests.test_trial_period -v`
Expected: все тесты, включая новые 2 из `ReminderKeyTests` — `ok`.

- [ ] **Step 5: Commit**

```bash
git add celery_app/subscription_lifecycle_service.py tests/test_trial_period.py
git commit -m "feat: separate trial_* reminder texts in subscription lifecycle check"
```

---

### Task 3: Хелпер доступности триала

**Files:**
- Modify: `bot/utils/onboarding.py`
- Modify: `tests/test_trial_period.py`

**Interfaces:**
- Consumes: `database.users_repository.db.get_user(tg_id: int) -> dict | None` (существующий метод)
- Produces: `bot.utils.onboarding.is_trial_available(tg_id: int) -> bool`

Общий хелпер для обеих точек входа (главное меню и профиль без подписки) — избегаем дублирования
условия `is_subscriber == False and wait_sub_confirmation == False and trial_used == False`.

- [ ] **Step 1: Написать падающие тесты**

Добавить в `tests/test_trial_period.py`:

```python
from unittest.mock import patch


class IsTrialAvailableTests(unittest.IsolatedAsyncioTestCase):
    async def test_available_for_new_user(self):
        from bot.utils.onboarding import is_trial_available

        with patch("database.users_repository.db.get_user", new=AsyncMock(return_value=None)):
            self.assertTrue(await is_trial_available(123))

    async def test_unavailable_when_subscriber(self):
        from bot.utils.onboarding import is_trial_available

        user = {"subscription_data": {"subscription": True, "wait_sub_confirmation": False, "trial_used": False}}
        with patch("database.users_repository.db.get_user", new=AsyncMock(return_value=user)):
            self.assertFalse(await is_trial_available(123))

    async def test_unavailable_when_wait_confirmation(self):
        from bot.utils.onboarding import is_trial_available

        user = {"subscription_data": {"subscription": False, "wait_sub_confirmation": True, "trial_used": False}}
        with patch("database.users_repository.db.get_user", new=AsyncMock(return_value=user)):
            self.assertFalse(await is_trial_available(123))

    async def test_unavailable_when_trial_used(self):
        from bot.utils.onboarding import is_trial_available

        user = {"subscription_data": {"subscription": False, "wait_sub_confirmation": False, "trial_used": True}}
        with patch("database.users_repository.db.get_user", new=AsyncMock(return_value=user)):
            self.assertFalse(await is_trial_available(123))

    async def test_available_when_nothing_used_yet(self):
        from bot.utils.onboarding import is_trial_available

        user = {"subscription_data": {"subscription": False, "wait_sub_confirmation": False, "trial_used": False}}
        with patch("database.users_repository.db.get_user", new=AsyncMock(return_value=user)):
            self.assertTrue(await is_trial_available(123))
```

- [ ] **Step 2: Запустить тесты и убедиться, что они падают**

Run: `python -m unittest tests.test_trial_period.IsTrialAvailableTests -v`
Expected: `FAIL` / `ImportError` — `is_trial_available` ещё не существует.

- [ ] **Step 3: Реализовать `is_trial_available`**

В `bot/utils/onboarding.py`, добавить в конец файла (после `is_trading_features_unlocked`):

```python
async def is_trial_available(tg_id: int) -> bool:
    """
    Доступен ли бесплатный пробный период: нет активной подписки, не в ожидании
    подтверждения оплаты, ещё не использовал триал.
    """
    from database.users_repository import db

    user = await db.get_user(tg_id)
    if user is None:
        return True
    subscription_data = user.get("subscription_data") or {}
    if subscription_data.get("subscription"):
        return False
    if subscription_data.get("wait_sub_confirmation"):
        return False
    return not subscription_data.get("trial_used")
```

- [ ] **Step 4: Запустить тесты и убедиться, что они проходят**

Run: `python -m unittest tests.test_trial_period -v`
Expected: все тесты — `ok`.

- [ ] **Step 5: Commit**

```bash
git add bot/utils/onboarding.py tests/test_trial_period.py
git commit -m "feat: is_trial_available helper (shared eligibility check for trial CTA)"
```

---

### Task 4: Тексты для триала (ru/en)

**Files:**
- Modify: `bot/languages/ru.py`
- Modify: `bot/languages/en.py`

Без unit-теста: языковые словари — статические данные, в кодбейзе не тестируются (нет
`test_languages.py`); корректность проверяется визуально в Task 9 (ручная проверка).

- [ ] **Step 1: Добавить ключи в `bot/languages/ru.py`**

В секцию `"start_btn"` (после `"prolong_subscription": "🔄 Продлить подписку",`) добавить:
```python
    "trial_start": "🎁 Попробовать бесплатно 7 дней",
```

В секцию `"subscription_text"` (после `"subscription_expired"`, перед закрывающей `},` секции)
добавить:
```python
    "trial_start_confirm": (
        "🎁 Активировать бесплатный пробный период на 7 дней?\n\n"
        "Полный доступ к торговле, как при подписке. Доступно только один раз."
    ),
    "trial_activated_success": (
        "🎉 Пробный период активирован! У вас есть 7 дней полного доступа — "
        "настройте API-ключ Bybit и сумму сделки, чтобы начать торговать."
    ),
    "trial_already_used": "Вы уже использовали бесплатный пробный период. Оформите подписку, чтобы продолжить.",
    "trial_reminder_3d": (
        "⏳ Ваш бесплатный пробный период завершается через 3 дня ({end_date}) — "
        "оформите подписку, чтобы не потерять доступ."
    ),
    "trial_reminder_1d": (
        "⏳ Ваш бесплатный пробный период завершается через 1 день ({end_date}) — "
        "оформите подписку, чтобы не потерять доступ."
    ),
    "trial_expired": (
        "⌛️ Ваш бесплатный пробный период закончился ({end_date}). "
        "Оформите подписку, чтобы продолжить пользоваться алгоритмом."
    ),
```

В секцию `"subscription_btn"` (после `"reject_payment": "✏️ Исправить ID",`) добавить:
```python
    "trial_confirm": "✅ Да, активировать",
    "trial_cancel": "❌ Отмена",
```

В секцию `"profile_btn"` (после `"subscription_buy": "💳 Оформить подписку",`) добавить:
```python
    "trial_start": "🎁 Попробовать бесплатно 7 дней",
```

В секцию `"admin_text"` (после `"toggle_unlimited_trade_removed"`, перед закрывающей `},`) добавить:
```python
    "trial_granted": "🎁 Пробный период выдан.",
    "trial_already_used": "Пользователь уже использовал пробный период.",
    "trial_reset": "♻️ Флаг использования триала сброшен.",
```

В секцию `"admin_btn"` (после `"toggle_unlimited_trade_removed"` или в конце секции, перед
закрывающей `},`) добавить:
```python
    "grant_trial": "🎁 Выдать триал вручную",
    "reset_trial": "♻️ Сбросить флаг использования триала",
```

- [ ] **Step 2: Добавить те же ключи в `bot/languages/en.py`**

В `"start_btn"`:
```python
    "trial_start": "🎁 Try free for 7 days",
```

В `"subscription_text"` (после `"subscription_expired"`):
```python
    "trial_start_confirm": (
        "🎁 Activate the free 7-day trial?\n\n"
        "Full trading access, same as a subscription. Available once only."
    ),
    "trial_activated_success": (
        "🎉 Trial activated! You have 7 days of full access — "
        "set up your Bybit API key and trade amount to start trading."
    ),
    "trial_already_used": "You have already used the free trial. Subscribe to continue.",
    "trial_reminder_3d": (
        "⏳ Your free trial ends in 3 days ({end_date}) — "
        "subscribe to keep access."
    ),
    "trial_reminder_1d": (
        "⏳ Your free trial ends in 1 day ({end_date}) — "
        "subscribe to keep access."
    ),
    "trial_expired": (
        "⌛️ Your free trial has ended ({end_date}). "
        "Subscribe to keep using the algorithm."
    ),
```

В `"subscription_btn"`:
```python
    "trial_confirm": "✅ Yes, activate",
    "trial_cancel": "❌ Cancel",
```

В `"profile_btn"`:
```python
    "trial_start": "🎁 Try free for 7 days",
```

В `"admin_text"`:
```python
    "trial_granted": "🎁 Trial granted.",
    "trial_already_used": "User has already used the trial.",
    "trial_reset": "♻️ Trial usage flag reset.",
```

В `"admin_btn"`:
```python
    "grant_trial": "🎁 Grant trial manually",
    "reset_trial": "♻️ Reset trial usage flag",
```

- [ ] **Step 3: Смоук-проверка, что оба файла синтаксически валидны**

Run: `python -c "from bot.languages.ru import RU_CONFIGURATION; from bot.languages.en import EN_CONFIGURATION; print(RU_CONFIGURATION['subscription_text']['trial_expired']); print(EN_CONFIGURATION['admin_btn']['grant_trial'])"`
Expected: печатает оба текста без исключений.

- [ ] **Step 4: Commit**

```bash
git add bot/languages/ru.py bot/languages/en.py
git commit -m "feat: add trial-period texts (ru/en)"
```

---

### Task 5: Callback-классы админки + клавиатуры (пользовательские и админские)

**Files:**
- Modify: `bot/callback_data/admin_lists.py`
- Modify: `bot/keyboards/inline_kb.py`

**Interfaces:**
- Produces: `bot.callback_data.admin_lists.AdminGrantTrialCb(tg_id: int)`,
  `bot.callback_data.admin_lists.AdminResetTrialCb(tg_id: int)`,
  `bot.keyboards.inline_kb.trial_start_kb(lang: str) -> InlineKeyboardBuilder`
- Consumes: `bot.utils.onboarding.is_trial_available(tg_id: int) -> bool` (Task 3),
  `database.users_repository.db.get_trial_used(tg_id: int) -> bool` (Task 1)

Без unit-теста для клавиатур: в кодбейзе нет тестов для `inline_kb.py` (визуальные UI-конструкторы,
проверяются вручную в Task 9).

- [ ] **Step 1: Добавить callback-классы**

В `bot/callback_data/admin_lists.py`, в конец файла (после `AdminCancelProlongSubscriptionCb`):

```python
class AdminGrantTrialCb(CallbackData, prefix="agtr"):
    tg_id: int


class AdminResetTrialCb(CallbackData, prefix="artr"):
    tg_id: int
```

- [ ] **Step 2: Импортировать новые callback-классы и хелпер в `inline_kb.py`**

В `bot/keyboards/inline_kb.py`, было:
```python
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    ActiveTradeItemCb,
    ActiveTradesPageCb,
    AdminCancelProlongSubscriptionCb,
    AdminCancelSubscriptionCb,
    AdminConfirmSubscriptionCb,
    AdminProlongSubscriptionCb,
    HISTORY_TRADES_PAGE_SIZE,
    HistoryTradeItemCb,
    HistoryTradesPageCb,
    SubscribersListPageCb,
    SubscribersUserCb,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
)
from database.users_repository import db
from database.app_settings_repository import app_settings_db
from config import URL_TGCHANNEL, URL_TECH_SUPPORT
```
Стало:
```python
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    ActiveTradeItemCb,
    ActiveTradesPageCb,
    AdminCancelProlongSubscriptionCb,
    AdminCancelSubscriptionCb,
    AdminConfirmSubscriptionCb,
    AdminGrantTrialCb,
    AdminProlongSubscriptionCb,
    AdminResetTrialCb,
    HISTORY_TRADES_PAGE_SIZE,
    HistoryTradeItemCb,
    HistoryTradesPageCb,
    SubscribersListPageCb,
    SubscribersUserCb,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
)
from bot.utils.onboarding import is_trial_available
from database.users_repository import db
from database.app_settings_repository import app_settings_db
from config import URL_TGCHANNEL, URL_TECH_SUPPORT
```

- [ ] **Step 3: Добавить кнопку триала в профиль без подписки**

В `bot/keyboards/inline_kb.py`, `profile_menu_kb_without_subscription` — было:
```python
async def profile_menu_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в профиле без подписки."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["subscription_buy"], callback_data="subscription_buy")
    kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb
```
Стало:
```python
async def profile_menu_kb_without_subscription(user_id: int, lang: str) -> InlineKeyboardBuilder:
    """Кнопки в профиле без подписки."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["profile_btn"]["subscription_buy"], callback_data="subscription_buy")
    if await is_trial_available(user_id):
        kb.button(text=cfg["profile_btn"]["trial_start"], callback_data="trial_start")
    kb.button(text=cfg["profile_btn"]["tech_support"], url=URL_TECH_SUPPORT)
    kb.button(text=cfg["general"]["main_menu"], callback_data="greeting")
    kb.adjust(1)
    return kb
```

- [ ] **Step 4: Добавить клавиатуру экрана-подтверждения триала**

В `bot/keyboards/inline_kb.py`, сразу после `profile_menu_kb_without_subscription`, добавить новую
функцию:

```python
async def trial_start_kb(lang: str) -> InlineKeyboardBuilder:
    """Подтверждение активации бесплатного пробного периода."""
    cfg = await get_config_lang(lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["subscription_btn"]["trial_confirm"], callback_data="trial_start_confirm")
    kb.button(text=cfg["subscription_btn"]["trial_cancel"], callback_data="trial_start_cancel")
    kb.adjust(1)
    return kb
```

- [ ] **Step 5: Добавить кнопки выдачи/сброса триала в карточку пользователя в админке**

В `bot/keyboards/inline_kb.py`, `positive_proccess_search_subscribers_kb` — было:
```python
    if target_tg_id is not None:
        is_unlimited = await app_settings_db.is_unlimited_trade_amount(int(target_tg_id))
        if is_unlimited:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_remove"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
        else:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_add"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
    kb.button(text=cfg["admin_btn"]["search_subscribers_again"], callback_data="search_subscribers_by_username_id")
```
Стало (добавлен блок выдачи/сброса триала внутри того же `if target_tg_id is not None:`):
```python
    if target_tg_id is not None:
        is_unlimited = await app_settings_db.is_unlimited_trade_amount(int(target_tg_id))
        if is_unlimited:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_remove"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
        else:
            kb.button(
                text=cfg["admin_btn"]["toggle_unlimited_trade_add"],
                callback_data="admin_toggle_unlimited_trade_amount",
            )
        trial_used = await db.get_trial_used(int(target_tg_id))
        if trial_used:
            kb.button(
                text=cfg["admin_btn"]["reset_trial"],
                callback_data=AdminResetTrialCb(tg_id=int(target_tg_id)),
            )
        else:
            kb.button(
                text=cfg["admin_btn"]["grant_trial"],
                callback_data=AdminGrantTrialCb(tg_id=int(target_tg_id)),
            )
    kb.button(text=cfg["admin_btn"]["search_subscribers_again"], callback_data="search_subscribers_by_username_id")
```

Эта кнопка размещена именно в `positive_proccess_search_subscribers_kb` (карточка "main" из поиска
подписчиков), а не в `subscription_settings_kb` — потому что `subscription_settings_kb` доступна
только для **уже подписанных** пользователей (гейт в обработчике `subscription_settings` в
`admin.py`), а выдавать триал нужно именно **не-подписчикам**. Карточка "main" доступна для любого
найденного пользователя независимо от статуса подписки.

- [ ] **Step 6: Смоук-проверка импорта**

Run: `python -c "import bot.keyboards.inline_kb"`
Expected: без исключений.

- [ ] **Step 7: Commit**

```bash
git add bot/callback_data/admin_lists.py bot/keyboards/inline_kb.py
git commit -m "feat: trial callback-data classes + keyboards (user + admin)"
```

---

### Task 6: Кнопка триала в главном меню

**Files:**
- Modify: `bot/utils/main_menu.py`

**Interfaces:**
- Consumes: `bot.utils.onboarding.is_trial_available(tg_id: int) -> bool` (Task 3)

- [ ] **Step 1: Добавить кнопку**

В `bot/utils/main_menu.py`, было:
```python
from bot.languages._lang_func import get_config_lang
from bot.utils.onboarding import build_onboarding_checklist
from config import URL_TGCHANNEL, ADMIN_IDS
from database.users_repository import db


async def build_main_menu_keyboard(user_id: int, lang: str) -> InlineKeyboardMarkup:
    cfg = await get_config_lang(lang)
    is_subscriber = await db.is_subscriber(user_id)
    wait_confirm = await db.is_wait_sub_confirmation(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["start_btn"]["url_tg"], url=URL_TGCHANNEL)

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["personal_account"], callback_data="profile_menu")
    elif wait_confirm:
        kb.button(text=cfg["start_btn"]["onboarding_setup"], callback_data="profile_menu")
    else:
        kb.button(text=cfg["start_btn"]["onboarding_progress"], callback_data="profile_menu")

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["prolong_subscription"], callback_data="prolong_subscription")
    elif not wait_confirm:
        kb.button(text=cfg["start_btn"]["subscription_buy"], callback_data="subscription_buy")

    if int(user_id) in ADMIN_IDS:
        kb.button(text=cfg["general"]["admin_panel"], callback_data="admin_menu")

    kb.button(text=cfg["general"]["change_language"], callback_data="start_menu")
    kb.adjust(1)
    return kb.as_markup()
```
Стало:
```python
from bot.languages._lang_func import get_config_lang
from bot.utils.onboarding import build_onboarding_checklist, is_trial_available
from config import URL_TGCHANNEL, ADMIN_IDS
from database.users_repository import db


async def build_main_menu_keyboard(user_id: int, lang: str) -> InlineKeyboardMarkup:
    cfg = await get_config_lang(lang)
    is_subscriber = await db.is_subscriber(user_id)
    wait_confirm = await db.is_wait_sub_confirmation(user_id)

    kb = InlineKeyboardBuilder()
    kb.button(text=cfg["start_btn"]["url_tg"], url=URL_TGCHANNEL)

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["personal_account"], callback_data="profile_menu")
    elif wait_confirm:
        kb.button(text=cfg["start_btn"]["onboarding_setup"], callback_data="profile_menu")
    else:
        kb.button(text=cfg["start_btn"]["onboarding_progress"], callback_data="profile_menu")

    if is_subscriber and not wait_confirm:
        kb.button(text=cfg["start_btn"]["prolong_subscription"], callback_data="prolong_subscription")
    elif not wait_confirm:
        kb.button(text=cfg["start_btn"]["subscription_buy"], callback_data="subscription_buy")
        if await is_trial_available(user_id):
            kb.button(text=cfg["start_btn"]["trial_start"], callback_data="trial_start")

    if int(user_id) in ADMIN_IDS:
        kb.button(text=cfg["general"]["admin_panel"], callback_data="admin_menu")

    kb.button(text=cfg["general"]["change_language"], callback_data="start_menu")
    kb.adjust(1)
    return kb.as_markup()
```

Кнопка добавлена именно в ветку `elif not wait_confirm:` (там же, где `subscription_buy`) — это
уже гарантирует `not wait_confirm`; `is_trial_available` дополнительно проверяет `trial_used` и
(на всякий случай) `subscription` изнутри, так что двойной проверки `is_subscriber` здесь не нужно.

- [ ] **Step 2: Смоук-проверка импорта**

Run: `python -c "import bot.utils.main_menu"`
Expected: без исключений.

- [ ] **Step 3: Commit**

```bash
git add bot/utils/main_menu.py
git commit -m "feat: trial CTA button in main menu"
```

---

### Task 7: Пользовательский флоу активации триала

**Files:**
- Modify: `bot/handlers/subscription.py`

**Interfaces:**
- Consumes: `bot.keyboards.inline_kb.trial_start_kb(lang: str)` (Task 5),
  `bot.keyboards.inline_kb.profile_menu_kb_without_subscription(user_id: int, lang: str)` (существует),
  `bot.utils.profile_menu.build_profile_menu_view(user_id: int, lang: str) -> tuple[str, InlineKeyboardMarkup]`
  (существует), `database.users_repository.db.start_trial_period(tg_id: int) -> bool` (Task 1)

- [ ] **Step 1: Добавить импорты**

В `bot/handlers/subscription.py`, было:
```python
from bot.keyboards.inline_kb import (
    subscription_buy_kb,
    question_kb,
    input_payment_id_kb,
    input_payment_id_back_kb,
    confirm_payment_kb,
    confirm_payment_success_kb,
    prolong_subscription_kb,
    prolong_question_kb,
    prolong_input_payment_id_kb,
    prolong_input_payment_id_back_kb,
    prolong_confirm_payment_kb,

)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message, send_info_payment_to_admin
from bot.utils.payment_screen import send_payment_info_screen, replace_callback_message_with_text
from database.users_repository import db
```
Стало:
```python
from bot.keyboards.inline_kb import (
    subscription_buy_kb,
    question_kb,
    input_payment_id_kb,
    input_payment_id_back_kb,
    confirm_payment_kb,
    confirm_payment_success_kb,
    prolong_subscription_kb,
    prolong_question_kb,
    prolong_input_payment_id_kb,
    prolong_input_payment_id_back_kb,
    prolong_confirm_payment_kb,
    profile_menu_kb_without_subscription,
    trial_start_kb,

)
from logger_config import setup_logger
from bot.utils.helpers import safe_edit_message, send_info_payment_to_admin
from bot.utils.payment_screen import send_payment_info_screen, replace_callback_message_with_text
from bot.utils.profile_menu import build_profile_menu_view
from database.users_repository import db
```

- [ ] **Step 2: Добавить обработчики**

В конец `bot/handlers/subscription.py` (после последнего обработчика `prolong_confirm_payment`)
добавить:

```python

@router.callback_query(F.data == "trial_start")
async def trial_start(callback: CallbackQuery, lang: str):
    """Экран подтверждения активации бесплатного пробного периода."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""

    text_config = await get_config_lang(lang)
    text = text_config["subscription_text"]["trial_start_confirm"]

    await safe_edit_message(
        callback,
        text,
        reply_markup=(await trial_start_kb(lang)).as_markup(),
    )
    logger.info(f"Пользователь {user_id} ({username}) открыл подтверждение пробного периода")


@router.callback_query(F.data == "trial_start_confirm")
async def trial_start_confirm(callback: CallbackQuery, lang: str):
    """Активация бесплатного пробного периода (self-service, без участия админа)."""
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)

    granted = await db.start_trial_period(user_id)
    if not granted:
        await callback.answer()
        await safe_edit_message(
            callback,
            text_config["subscription_text"]["trial_already_used"],
            reply_markup=(await profile_menu_kb_without_subscription(user_id, lang)).as_markup(),
        )
        logger.info(f"Пользователь {user_id} ({username}) повторно запросил уже использованный триал")
        return

    await callback.answer()
    text, markup = await build_profile_menu_view(user_id, lang)
    await safe_edit_message(callback, text, reply_markup=markup)
    logger.info(f"Пользователь {user_id} ({username}) активировал бесплатный пробный период")


@router.callback_query(F.data == "trial_start_cancel")
async def trial_start_cancel(callback: CallbackQuery, lang: str):
    """Отмена активации пробного периода — назад в профиль."""
    user_id = callback.from_user.id
    text, markup = await build_profile_menu_view(user_id, lang)
    await safe_edit_message(callback, text, reply_markup=markup)
```

- [ ] **Step 3: Смоук-проверка импорта**

Run: `python -c "import bot.handlers.subscription"`
Expected: без исключений.

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/subscription.py
git commit -m "feat: user-facing trial activation flow (confirm screen + handlers)"
```

---

### Task 8: Админский флоу выдачи/сброса триала

**Files:**
- Modify: `bot/handlers/admin.py`

**Interfaces:**
- Consumes: `bot.callback_data.admin_lists.{AdminGrantTrialCb,AdminResetTrialCb}` (Task 5),
  `database.users_repository.db.{start_trial_period,admin_reset_trial_used}` (Task 1),
  `bot.utils.helpers.notify_user_telegram(bot, tg_id: int, text: str, reply_markup=None) -> bool`
  (существует), `bot.keyboards.inline_kb.positive_proccess_search_subscribers_kb` (существует,
  используется тем же способом, что и в остальных обработчиках админ-карточки)

- [ ] **Step 1: Добавить импорты**

В `bot/handlers/admin.py`, было:
```python
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
    AdminOpenUserCb,
    AdminConfirmSubscriptionCb,
    AdminCancelSubscriptionCb,
    AdminProlongSubscriptionCb,
    AdminCancelProlongSubscriptionCb,
    SubscribersListPageCb,
    SubscribersUserCb,
)
from bot.utils.helpers import safe_edit_message, notify_user_telegram
from bot.utils.misc import _format_dt
from bot.states.admin_states import AdminStates
from database.users_repository import db, UsersRepositoryError, ValidationError
```
Стало:
```python
from bot.callback_data.admin_lists import (
    ADMIN_LIST_PAGE_SIZE,
    WaitConfirmListPageCb,
    WaitConfirmUserCb,
    AdminOpenUserCb,
    AdminConfirmSubscriptionCb,
    AdminCancelSubscriptionCb,
    AdminGrantTrialCb,
    AdminProlongSubscriptionCb,
    AdminCancelProlongSubscriptionCb,
    AdminResetTrialCb,
    SubscribersListPageCb,
    SubscribersUserCb,
)
from bot.utils.helpers import safe_edit_message, notify_user_telegram
from bot.utils.misc import _format_dt
from bot.states.admin_states import AdminStates
from database.users_repository import db, UsersRepositoryError, ValidationError
```

- [ ] **Step 2: Добавить обработчики**

В `bot/handlers/admin.py`, сразу после обработчика `cancel_subscription`
(`@router.callback_query(AdminCancelSubscriptionCb.filter())`, ищем конец его тела — следующая
строка кода после последнего `logger.info(...)` этого обработчика), добавить:

```python
@router.callback_query(AdminGrantTrialCb.filter())
async def admin_grant_trial(
    callback: CallbackQuery,
    callback_data: AdminGrantTrialCb,
    state: FSMContext,
    lang: str,
):
    """Админ выдаёт пробный период вручную (например, по просьбе в техподдержку)."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    target_tg_id = int(callback_data.tg_id)

    try:
        granted = await db.start_trial_period(target_tg_id)
    except UsersRepositoryError as e:
        await callback.answer(f"Не удалось выдать триал: {e}", show_alert=True)
        return

    if not granted:
        await callback.answer(text_config["admin_text"]["trial_already_used"], show_alert=True)
        return

    user = await db.get_user(target_tg_id)
    if user is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return

    await callback.answer(text_config["admin_text"]["trial_granted"], show_alert=True)
    await safe_edit_message(
        callback,
        _format_admin_subscribers_text_by_template(_user_doc_for_template(user), text_config, "main"),
        reply_markup=(
            await positive_proccess_search_subscribers_kb(lang, target_tg_id=target_tg_id)
        ).as_markup(),
    )
    await notify_user_telegram(
        callback.bot, target_tg_id, text_config["subscription_text"]["trial_activated_success"]
    )
    logger.info(
        "Админ %s (%s) вручную выдал пробный период пользователю %s",
        admin_user_id,
        admin_username,
        target_tg_id,
    )


@router.callback_query(AdminResetTrialCb.filter())
async def admin_reset_trial(
    callback: CallbackQuery,
    callback_data: AdminResetTrialCb,
    state: FSMContext,
    lang: str,
):
    """Админ сбрасывает флаг использования триала (повторный триал по просьбе в техподдержку)."""
    admin_user_id = callback.from_user.id
    admin_username = callback.from_user.username or ""
    text_config = await get_config_lang(lang)
    target_tg_id = int(callback_data.tg_id)

    try:
        await db.admin_reset_trial_used(target_tg_id)
    except (ValidationError, UsersRepositoryError) as e:
        await callback.answer(f"Не удалось сбросить флаг триала: {e}", show_alert=True)
        return

    user = await db.get_user(target_tg_id)
    if user is None:
        await callback.answer(text_config["admin_text"]["error_user_not_found"], show_alert=True)
        return

    await callback.answer(text_config["admin_text"]["trial_reset"], show_alert=True)
    await safe_edit_message(
        callback,
        _format_admin_subscribers_text_by_template(_user_doc_for_template(user), text_config, "main"),
        reply_markup=(
            await positive_proccess_search_subscribers_kb(lang, target_tg_id=target_tg_id)
        ).as_markup(),
    )
    logger.info(
        "Админ %s (%s) сбросил флаг использования триала пользователю %s",
        admin_user_id,
        admin_username,
        target_tg_id,
    )
```

- [ ] **Step 3: Смоук-проверка импорта**

Run: `python -c "import bot.handlers.admin"`
Expected: без исключений.

- [ ] **Step 4: Commit**

```bash
git add bot/handlers/admin.py
git commit -m "feat: admin grant/reset trial handlers"
```

---

### Task 9: Полный прогон тестов + ручная проверка (Manual — не автоматизируется)

**Files:** нет новых изменений кода — финальная верификация всей фичи.

- [ ] **Step 1: Прогнать весь набор unit-тестов проекта**

Run: `python -m unittest tests.test_trial_period tests.test_trade_orchestrator tests.test_redis_market_keys tests.test_dual_feed_failover tests.test_redis_price_subscriber -v`
Expected: все тесты — `ok` (новые тесты триала не сломали существующие).

- [ ] **Step 2: Ручная проверка self-service флоу**

В боте (тестовый tg_id без подписки):
1. `/start` → убедиться, что кнопка «🎁 Попробовать бесплатно 7 дней» видна рядом с «Оформить подписку».
2. Открыть профиль без подписки → та же кнопка видна там же.
3. Тап по кнопке → экран-подтверждение с «Да, активировать»/«Отмена».
4. «Отмена» → возврат в профиль без подписки, кнопка триала всё ещё видна.
5. Повторный тап → «Да, активировать» → должен открыться полный профиль (как при подписке),
   `Тип: trial` в профиле (если поле показывается в профильном шаблоне).
6. Вернуться на `/start` и в профиль без подписки другого раза — кнопка триала **не должна
   отображаться** (уже использован).
7. Попытаться вызвать `db.start_trial_period(<тот же tg_id>)` повторно напрямую (например, через
   `python -c` с реальным Mongo) — должно вернуть `False`.

- [ ] **Step 3: Проверить попадание триал-пользователя в торговлю**

С активным триалом и настроенными API-ключами — убедиться, что пользователь появляется в
`db.list_trading_candidates()` (например, временный скрипт `python -c` с реальным Mongo) наравне с
обычными подписчиками.

- [ ] **Step 4: Ручная проверка Celery Beat напоминаний**

На тестовом документе пользователя с `subscription_type=trial` подменить `end_subscription_date` на
"через 3 дня" / "через 1 день" / "в прошлом", прогнать:

```bash
celery -A celery_app.celery_config call check_subscription_lifecycle
```

Проверить в Telegram: тексты `trial_reminder_3d`/`trial_reminder_1d`/`trial_expired` (не
`subscription_*`), и что по истечении `subscription_data.subscription` стало `False`
(доступ к торговле пропал).

- [ ] **Step 5: Ручная проверка админского флоу**

В админке — найти пользователя без подписки и без использованного триала → в карточке должна быть
кнопка «🎁 Выдать триал вручную». Нажать → убедиться, что пользователь получил уведомление в
Telegram и в карточке теперь кнопка сменилась на «♻️ Сбросить флаг использования триала». Нажать её →
убедиться, что кнопка вернулась к «Выдать триал вручную», и что у пользователя в боте снова
появилась кнопка «Попробовать бесплатно».

---

## Self-Review

**Spec coverage:** все разделы спеки (`docs/superpowers/specs/2026-08-11-trial-period-design.md`)
покрыты: модель данных и `start_trial_period` — Task 1; переиспользование
`list_trading_candidates`/`deactivate_subscription` без изменений — явно задокументировано в Global
Constraints, ни один task их не трогает; точки входа (главное меню + профиль) — Tasks 5–7; UX
экрана-подтверждения — Task 7; отдельные тексты уведомлений — Tasks 2, 4; админ-контроль — Tasks 5, 8;
тестирование — Tasks 1–3 (unit) + Task 9 (manual/integration).

**Placeholder scan:** нет TBD/TODO, каждый шаг с кодом содержит полный реальный код (не "аналогично
Task N" без кода).

**Type consistency:** `start_trial_period(tg_id: int) -> bool` — одинаковая сигнатура в Task 1
(реализация + тест), Task 7 (`db.start_trial_period(user_id)`), Task 8
(`db.start_trial_period(target_tg_id)`). `is_trial_available(tg_id: int) -> bool` — одинаково
объявлена в Task 3 и потреблена в Task 5 (`inline_kb.py`) и Task 6 (`main_menu.py`).
`AdminGrantTrialCb`/`AdminResetTrialCb` — поле `tg_id: int` одинаково в Task 5 (объявление) и Task 8
(`callback_data.tg_id`). Callback-строки `"trial_start"`/`"trial_start_confirm"`/`"trial_start_cancel"`
совпадают между Task 5 (клавиатуры) и Task 7 (обработчики).

**Найденный при планировании нюанс:** первоначально кнопки «Выдать триал»/«Сбросить флаг» планировались
в `subscription_settings_kb`, но эта клавиатура в текущем коде доступна только для **уже
подписанных** пользователей (гейт в обработчике `subscription_settings`) — то есть именно для той
категории, которой выдача триала не нужна. Перенесено в `positive_proccess_search_subscribers_kb`
(карточка "main" из поиска — доступна для любого найденного пользователя независимо от статуса
подписки), см. Task 5 Step 5.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-12-trial-period.md`.**
