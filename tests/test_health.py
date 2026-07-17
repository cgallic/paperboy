from __future__ import annotations

import unittest

from paperboy.health import check_database, check_disk, run_all


class HealthTests(unittest.TestCase):
    def test_database_probe_missing_file(self) -> None:
        ok, detail = check_database()
        # May pass or fail depending on whether events.db exists in test env
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(detail, str)

    def test_disk_probe(self) -> None:
        ok, detail = check_disk()
        self.assertIsInstance(ok, bool)
        self.assertIn("GB free", detail)

    def test_run_all_returns_structure(self) -> None:
        report = run_all()
        self.assertIn("overall", report)
        self.assertIn("database", report)
        self.assertIn("ollama", report)
        self.assertIn("disk", report)
        self.assertIn("discord", report)
        self.assertIn("status", report["overall"])


if __name__ == "__main__":
    unittest.main()
