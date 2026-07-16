from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

from paperboy.config import settings
from paperboy.email.sender import _create_smtp_connection, send_raw


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

    def test_plaintext_smtp_requires_explicit_starttls_opt_out(self) -> None:
        old_host = settings.smtp_host
        old_port = settings.smtp_port
        old_starttls = settings.smtp_starttls
        connection = MagicMock()
        try:
            settings.smtp_host = "host.docker.internal"
            settings.smtp_port = 25
            settings.smtp_starttls = False
            with patch("paperboy.email.sender.smtplib.SMTP", return_value=connection) as smtp:
                result = _create_smtp_connection()
            self.assertIs(result, connection)
            smtp.assert_called_once_with("host.docker.internal", 25, timeout=30)
            connection.starttls.assert_not_called()
        finally:
            settings.smtp_host = old_host
            settings.smtp_port = old_port
            settings.smtp_starttls = old_starttls


if __name__ == "__main__":
    unittest.main()
