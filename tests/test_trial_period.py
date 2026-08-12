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


if __name__ == "__main__":
    unittest.main()
