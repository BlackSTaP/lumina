"""Regression tests for Telegram schedule text formats."""
import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

from scraper import parse_post


class ScheduleFormatTests(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 11, 3)
        self.published = datetime(2026, 11, 3, 10, 0, tzinfo=ZoneInfo("Europe/Kyiv"))

    def test_multiline_message_without_date(self):
        message = """⚡ Черга 1.1
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 1.2
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 2.1
з 06:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30

⚡ Черга 2.2
з 06:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30

⚡ Черга 3.1
з 06:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30

⚡ Черга 3.2
з 05:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30

⚡ Черга 4.1
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 4.2
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 5.1
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 5.2
з 09:00 до 13:00
з 16:00 до 20:00

⚡ Черга 6.1
з 06:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30

⚡ Черга 6.2
з 05:30 до 09:30
з 12:30 до 16:30
з 19:30 до 22:30"""
        parsed = parse_post(message, self.today, self.published)
        self.assertIsNotNone(parsed)
        day, queues = parsed
        self.assertEqual(day, self.today)
        self.assertEqual(len(queues), 12)
        self.assertEqual(queues["1.1"], "09:00 - 13:00, 16:00 - 20:00")
        self.assertEqual(queues["2.1"], "06:30 - 09:30, 12:30 - 16:30, 19:30 - 22:30")
        self.assertEqual(queues["6.2"], "05:30 - 09:30, 12:30 - 16:30, 19:30 - 22:30")

    def test_existing_inline_format(self):
        parsed = parse_post("ГПВ на 3 листопада\nЧерга 1.1: з 09:00 до 13:00, з 16:00 до 20:00\n1.2: 09:00-13:00", self.today, self.published)
        self.assertEqual(parsed[1]["1.1"], "09:00 - 13:00, 16:00 - 20:00")
        self.assertEqual(parsed[1]["1.2"], "09:00 - 13:00")

    def test_tomorrow_and_numeric_dates(self):
        self.assertEqual(parse_post("Графік на завтра\nЧерга 1.1\nз 10:00 до 13:00", self.today, self.published)[0], date(2026, 11, 4))
        self.assertEqual(parse_post("04.11.2026\n⚡ Черга 1.1\n10:00 – 13:00", self.today, self.published)[0], date(2026, 11, 4))

    def test_ignores_invalid_times_and_unrelated_text(self):
        parsed = parse_post("⚡ Черга 1.1\nз 25:00 до 26:00\nз 09:00 до 13:00\nПримітка: зміни можливі\n12:00 до 14:00", self.today, self.published)
        self.assertEqual(parsed[1], {"1.1": "09:00 - 13:00"})

    def test_no_schedule(self):
        self.assertIsNone(parse_post("⚡ Черга 1.1\nПоки без інформації", self.today, self.published))


if __name__ == "__main__":
    unittest.main()
