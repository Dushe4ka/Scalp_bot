import logging
import unittest
from unittest.mock import MagicMock, patch

import requests

from celery_app import api_key_lifecycle_service, subscription_lifecycle_service


def _eager_result(successful: bool, result):
    r = MagicMock()
    r.successful.return_value = successful
    r.result = result
    return r


class SubscriptionSendNotificationTests(unittest.TestCase):
    def test_success_returns_true(self):
        with patch(
            "celery_app.tasks.notifications.send_notification_to_user_task.apply",
            return_value=_eager_result(True, {"ok": True, "tg_id": 1}),
        ):
            self.assertTrue(subscription_lifecycle_service._send_user_notification(1, "hi"))

    def test_failed_task_logs_real_error_not_attributeerror(self):
        http_error = requests.exceptions.HTTPError("403 Client Error: Forbidden")
        with patch(
            "celery_app.tasks.notifications.send_notification_to_user_task.apply",
            return_value=_eager_result(False, http_error),
        ):
            with self.assertLogs(subscription_lifecycle_service.logger, level="ERROR") as cm:
                ok = subscription_lifecycle_service._send_user_notification(1, "hi")
        self.assertFalse(ok)
        logged = "\n".join(cm.output)
        self.assertIn("403 Client Error: Forbidden", logged)
        self.assertNotIn("has no attribute 'get'", logged)


class ApiKeySendNotificationTests(unittest.TestCase):
    def test_success_returns_true(self):
        with patch(
            "celery_app.tasks.notifications.send_notification_to_user_task.apply",
            return_value=_eager_result(True, {"ok": True, "tg_id": 1}),
        ):
            self.assertTrue(api_key_lifecycle_service._send_user_notification(1, "hi"))

    def test_failed_task_logs_real_error_not_attributeerror(self):
        http_error = requests.exceptions.HTTPError("403 Client Error: Forbidden")
        with patch(
            "celery_app.tasks.notifications.send_notification_to_user_task.apply",
            return_value=_eager_result(False, http_error),
        ):
            with self.assertLogs(api_key_lifecycle_service.logger, level="ERROR") as cm:
                ok = api_key_lifecycle_service._send_user_notification(1, "hi")
        self.assertFalse(ok)
        logged = "\n".join(cm.output)
        self.assertIn("403 Client Error: Forbidden", logged)
        self.assertNotIn("has no attribute 'get'", logged)


if __name__ == "__main__":
    unittest.main()
