from __future__ import annotations

import os
import unittest

from paperboy.email.sender import send_raw


class EmailTests(unittest.TestCase):
    def test_send_raw_no_recipient(self) -> None:
        os.environ["EMAIL_TO"] = ""
        result = send_raw("Test", "body", dry_run=True)
        self.assertFalse(result["ok"])
        self.assertIn("recipient", result["detail"])

    def test_send_raw_dry_run(self) -> None:
        result = send_raw("Test Subject", "Hello", to="dev@localhost", dry_run=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "dry_run")


if __name__ == "__main__":
    unittest.main()
