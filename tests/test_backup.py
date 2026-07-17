from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paperboy.backup import BackupError, create_backup, restore_backup, verify_backup
from paperboy.db import init_schema


class BackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state = self.root / "state"
        self.backups = self.root / "backups"
        self.database = self.state / "events.db"
        self.environment = patch.dict(
            os.environ,
            {
                "PAPERBOY_ROOT": str(self.state),
                "PAPERBOY_DB": str(self.database),
                "PAPERBOY_BACKUP_DIR": str(self.backups),
            },
            clear=False,
        )
        self.environment.start()
        os.environ.pop("PAPERBOY_MANAGE_SECRET", None)
        init_schema()
        secret = self.state / "manage-secret"
        secret.write_bytes(b"s" * 32)
        connection = sqlite3.connect(self.database)
        try:
            connection.execute(
                "INSERT INTO events(ts,source,type,actor,payload_json,attachment_uri,ingested_at) "
                "VALUES(?,?,?,?,?,?,?)",
                ("2026-07-17T00:00:00Z", "test", "backup", None, "{}", None, "2026-07-17T00:00:00Z"),
            )
            connection.commit()
        finally:
            connection.close()

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary.cleanup()

    def test_create_verify_and_restore_to_new_target(self) -> None:
        result = create_backup(retention_days=30)
        bundle = Path(result["bundle"])
        self.assertTrue(result["verified"])
        self.assertEqual(verify_backup(bundle)["integrity"], "ok")
        target = self.root / "restore-drill"
        restored = restore_backup(bundle, target)
        self.assertTrue(restored["restored"])
        self.assertEqual((target / "manage-secret").read_bytes(), b"s" * 32)
        connection = sqlite3.connect(target / "events.db")
        try:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        finally:
            connection.close()

    def test_verification_rejects_tampered_database(self) -> None:
        result = create_backup(retention_days=30)
        database = Path(result["bundle"]) / "events.db"
        with database.open("ab") as handle:
            handle.write(b"tampered")
        with self.assertRaisesRegex(BackupError, "checksum"):
            verify_backup(database.parent)

    def test_restore_refuses_existing_or_live_target(self) -> None:
        result = create_backup(retention_days=30)
        with self.assertRaisesRegex(BackupError, "must not already exist"):
            restore_backup(result["bundle"], self.state)

    def test_configured_management_secret_is_copied_without_exposure(self) -> None:
        configured = "configured-management-secret-is-long-enough"
        with patch.dict(os.environ, {"PAPERBOY_MANAGE_SECRET": configured}, clear=False):
            result = create_backup(retention_days=30)
        self.assertEqual((Path(result["bundle"]) / "manage-secret").read_bytes(), configured.encode())

    def test_retention_prunes_only_expired_valid_bundles(self) -> None:
        now = datetime(2026, 7, 17, tzinfo=timezone.utc)
        old = create_backup(retention_days=3650, now=now - timedelta(days=45))
        unrelated = self.backups / "do-not-delete"
        unrelated.mkdir()
        current = create_backup(retention_days=30, now=now)
        self.assertFalse(Path(old["bundle"]).exists())
        self.assertTrue((self.backups / ".expired" / Path(old["bundle"]).name).exists())
        self.assertTrue(Path(current["bundle"]).exists())
        self.assertTrue(unrelated.exists())
        self.assertEqual(current["pruned"], 1)


if __name__ == "__main__":
    unittest.main()
