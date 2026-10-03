import json
import unittest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apkt_monitor.defaults import DEFAULT_VARIABLES
from apkt_monitor.logic import date_range, get_path, render_variables, sanitize_text, should_remind


class TestLogic(unittest.TestCase):
    def test_window_covers_yesterday_after_midnight(self):
        now = datetime(2026, 10, 4, 1, 0, tzinfo=ZoneInfo("Asia/Jakarta"))
        self.assertEqual(date_range(1, "Asia/Jakarta", now), ("2026-10-03", "2026-10-04"))

    def test_window_uses_timezone_not_server_clock(self):
        utc = datetime(2026, 10, 3, 18, 30, tzinfo=ZoneInfo("UTC"))  # 01:30 WIB 4 Okt
        now = utc.astimezone(ZoneInfo("Asia/Jakarta"))
        self.assertEqual(date_range(1, "Asia/Jakarta", now)[1], "2026-10-04")

    def test_default_variables_render_valid_json(self):
        acc = {"user_id": 254456, "id_uid": 161, "id_up3": 163, "id_ulp": 16100}
        v = json.loads(render_variables(DEFAULT_VARIABLES, "2026-10-03", "2026-10-04", 100, 50, acc))
        self.assertEqual(v["search"]["skip"], 100)
        self.assertEqual(v["search"]["take"], 50)
        self.assertEqual(v["search"]["dateFrom"], "2026-10-03")
        self.assertEqual(v["search"]["filter"][1]["value"], [16100])
        self.assertEqual(v["idUid"], 161)

    def test_missing_variable_fails(self):
        with self.assertRaises(Exception):
            render_variables('{"a": {{ nope }}}', "2026-10-03", "2026-10-04", 0, 1, {})

    def test_reminder_rules(self):
        now = datetime(2026, 10, 4, 10, 0)
        m = 15
        self.assertFalse(should_remind(0, now - timedelta(minutes=14), None, now, m))
        self.assertTrue(should_remind(0, now - timedelta(minutes=15), None, now, m))
        self.assertFalse(should_remind(0, now - timedelta(minutes=40), now - timedelta(minutes=5), now, m))
        self.assertTrue(should_remind(0, now - timedelta(minutes=40), now - timedelta(minutes=15), now, m))
        self.assertFalse(should_remind(1, now - timedelta(hours=3), None, now, m))

    def test_helpers(self):
        self.assertEqual(get_path({"a": {"b": 1}}, "a.b"), 1)
        self.assertIsNone(get_path({"a": 1}, "a.b"))
        self.assertEqual(sanitize_text("*x* _y_\u202e"), "x y")
        self.assertEqual(sanitize_text(None), "-")


if __name__ == "__main__":
    unittest.main()
