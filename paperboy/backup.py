"""Verified online backups for Paperboy's SQLite state and signing key."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from paperboy.db import db_path, root

_BUNDLE_VERSION = 1
_DATABASE_NAME = "events.db"
_MANIFEST_NAME = "manifest.json"
_SECRET_NAME = "manage-secret"
_BUNDLE_PREFIX = "paperboy-"


class BackupError(RuntimeError):
    """A backup could not be created, verified, or restored safely."""


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise BackupError("backup timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_record(path: Path) -> dict[str, str | int]:
    return {"sha256": _sha256(path), "size": path.stat().st_size}


def _integrity_check(path: Path) -> None:
    try:
        connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True, timeout=30)
        try:
            result = connection.execute("PRAGMA integrity_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise BackupError("backup database could not be opened") from exc
    if result is None or result[0] != "ok":
        raise BackupError("backup database failed SQLite integrity_check")


def _management_secret() -> tuple[bytes, str]:
    configured = os.environ.get("PAPERBOY_MANAGE_SECRET")
    if configured:
        secret = configured.encode("utf-8")
        source = "environment"
    else:
        path = root() / _SECRET_NAME
        if not path.is_file():
            raise BackupError("Paperboy management secret is missing")
        secret = path.read_bytes()
        source = "file"
    if len(secret) < 32:
        raise BackupError("Paperboy management secret must be at least 32 bytes")
    return secret, source


def _backup_root(value: str | Path | None = None) -> Path:
    configured = value or os.environ.get("PAPERBOY_BACKUP_DIR") or "/app/backups"
    path = Path(configured).expanduser().resolve()
    if path == Path(path.anchor):
        raise BackupError("backup directory may not be a filesystem root")
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise BackupError("backup destination is not a directory")
    path.chmod(0o700)
    return path


def _bundle_file(bundle: Path, name: str) -> Path:
    if Path(name).name != name:
        raise BackupError("backup manifest contains an unsafe filename")
    path = (bundle / name).resolve()
    if path.parent != bundle:
        raise BackupError("backup manifest escaped its bundle")
    return path


def _load_manifest(bundle: Path) -> dict[str, Any]:
    manifest_path = _bundle_file(bundle, _MANIFEST_NAME)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError("backup manifest is unreadable") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != _BUNDLE_VERSION:
        raise BackupError("backup manifest version is unsupported")
    return manifest


def verify_backup(bundle: str | Path) -> dict[str, Any]:
    """Verify checksums, signing-key presence, and SQLite integrity."""
    requested = Path(bundle).expanduser()
    if requested.is_symlink():
        raise BackupError("backup bundle does not exist or is unsafe")
    bundle_path = requested.resolve()
    if not bundle_path.is_dir():
        raise BackupError("backup bundle does not exist or is unsafe")
    manifest = _load_manifest(bundle_path)
    records = manifest.get("files")
    if not isinstance(records, dict):
        raise BackupError("backup manifest has no file records")

    for name in (_DATABASE_NAME, _SECRET_NAME):
        record = records.get(name)
        if not isinstance(record, dict):
            raise BackupError(f"backup manifest is missing {name}")
        path = _bundle_file(bundle_path, name)
        if not path.is_file() or path.is_symlink():
            raise BackupError(f"backup is missing {name}")
        if path.stat().st_size != record.get("size") or _sha256(path) != record.get("sha256"):
            raise BackupError(f"backup checksum failed for {name}")

    secret_path = _bundle_file(bundle_path, _SECRET_NAME)
    if secret_path.stat().st_size < 32:
        raise BackupError("backed-up management secret is too short")
    _integrity_check(_bundle_file(bundle_path, _DATABASE_NAME))
    return {
        "bundle": str(bundle_path),
        "created_at": manifest.get("created_at"),
        "files": len(records),
        "integrity": "ok",
        "verified": True,
    }


def _retention_days(value: int | None) -> int:
    raw = value if value is not None else os.environ.get("PAPERBOY_BACKUP_RETENTION_DAYS", "30")
    try:
        days = int(raw)
    except (TypeError, ValueError) as exc:
        raise BackupError("backup retention days must be an integer") from exc
    if days < 1 or days > 3650:
        raise BackupError("backup retention days must be between 1 and 3650")
    return days


def prune_backups(
    backup_dir: str | Path,
    *,
    retention_days: int,
    now: datetime | None = None,
    exclude: Path | None = None,
) -> int:
    """Quarantine expired, direct-child bundles without irreversibly deleting them."""
    backup_root = _backup_root(backup_dir)
    expired_root = backup_root / ".expired"
    cutoff = _utc_now(now) - timedelta(days=retention_days)
    excluded = exclude.resolve() if exclude else None
    pruned = 0
    for candidate in backup_root.iterdir():
        resolved = candidate.resolve()
        if (
            not candidate.name.startswith(_BUNDLE_PREFIX)
            or not candidate.is_dir()
            or candidate.is_symlink()
            or resolved.parent != backup_root
            or resolved == excluded
        ):
            continue
        try:
            manifest = _load_manifest(resolved)
            created_at = datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00"))
        except (BackupError, KeyError, TypeError, ValueError):
            continue
        if _utc_now(created_at) < cutoff:
            expired_root.mkdir(mode=0o700, exist_ok=True)
            destination = expired_root / candidate.name
            if destination.exists():
                continue
            os.replace(resolved, destination)
            pruned += 1
    return pruned


def create_backup(
    backup_dir: str | Path | None = None,
    *,
    retention_days: int | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create and verify an online SQLite backup, then apply retention."""
    created = _utc_now(now)
    destination_root = _backup_root(backup_dir)
    source_database = db_path().expanduser().resolve()
    if not source_database.is_file():
        raise BackupError("Paperboy database does not exist")
    secret, secret_source = _management_secret()
    name = created.strftime(f"{_BUNDLE_PREFIX}%Y%m%dT%H%M%S.%fZ")
    final_bundle = destination_root / name
    if final_bundle.exists():
        raise BackupError("backup destination already exists")
    staging = Path(tempfile.mkdtemp(prefix=".paperboy-backup-", dir=destination_root))
    try:
        backup_database = staging / _DATABASE_NAME
        source = sqlite3.connect(str(source_database), timeout=30)
        target = sqlite3.connect(str(backup_database), timeout=30)
        try:
            source.execute("PRAGMA query_only = ON")
            source.backup(target, pages=1024, sleep=0.01)
            target.commit()
        except sqlite3.Error as exc:
            raise BackupError("SQLite online backup failed") from exc
        finally:
            target.close()
            source.close()
        backup_database.chmod(0o600)

        secret_path = staging / _SECRET_NAME
        secret_path.write_bytes(secret)
        secret_path.chmod(0o600)
        _integrity_check(backup_database)
        manifest = {
            "version": _BUNDLE_VERSION,
            "created_at": _iso(created),
            "database": _DATABASE_NAME,
            "management_secret": _SECRET_NAME,
            "management_secret_source": secret_source,
            "sqlite_integrity": "ok",
            "files": {
                _DATABASE_NAME: _file_record(backup_database),
                _SECRET_NAME: _file_record(secret_path),
            },
        }
        manifest_path = staging / _MANIFEST_NAME
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        manifest_path.chmod(0o600)
        verify_backup(staging)
        os.replace(staging, final_bundle)
    except Exception:
        if staging.exists():
            failed_root = destination_root / ".failed"
            failed_root.mkdir(mode=0o700, exist_ok=True)
            os.replace(staging, failed_root / staging.name)
        raise

    result = verify_backup(final_bundle)
    result["pruned"] = prune_backups(
        destination_root,
        retention_days=_retention_days(retention_days),
        now=created,
        exclude=final_bundle,
    )
    return result


def restore_backup(bundle: str | Path, target_dir: str | Path) -> dict[str, Any]:
    """Restore a verified bundle into a new directory without touching live state."""
    bundle_path = Path(bundle).expanduser().resolve()
    verification = verify_backup(bundle_path)
    target = Path(target_dir).expanduser().resolve()
    live_database = db_path().expanduser().resolve()
    live_root = root().expanduser().resolve()
    if target.exists():
        raise BackupError("restore target must not already exist")
    if target == live_root or live_root in target.parents or target == live_database.parent:
        raise BackupError("restore target must be separate from live Paperboy state")
    if target == bundle_path or bundle_path in target.parents:
        raise BackupError("restore target must be separate from the backup bundle")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".paperboy-restore-", dir=target.parent))
    try:
        for name in (_DATABASE_NAME, _SECRET_NAME):
            restored = staging / name
            shutil.copyfile(_bundle_file(bundle_path, name), restored)
            restored.chmod(0o600)
        _integrity_check(staging / _DATABASE_NAME)
        if (staging / _SECRET_NAME).stat().st_size < 32:
            raise BackupError("restored management secret is too short")
        os.replace(staging, target)
    except Exception:
        if staging.exists():
            failed_root = target.parent / ".paperboy-failed-restores"
            failed_root.mkdir(mode=0o700, exist_ok=True)
            os.replace(staging, failed_root / staging.name)
        raise
    return {
        "bundle": verification["bundle"],
        "database": str(target / _DATABASE_NAME),
        "integrity": "ok",
        "restored": True,
        "target": str(target),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create and verify a backup")
    create.add_argument("--backup-dir")
    create.add_argument("--retention-days", type=int)
    verify = commands.add_parser("verify", help="verify an existing backup bundle")
    verify.add_argument("bundle")
    restore = commands.add_parser("restore", help="restore into a new, non-live target directory")
    restore.add_argument("bundle")
    restore.add_argument("--target-dir", required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    try:
        if args.command == "create":
            result = create_backup(args.backup_dir, retention_days=args.retention_days)
        elif args.command == "verify":
            result = verify_backup(args.bundle)
        else:
            result = restore_backup(args.bundle, args.target_dir)
    except BackupError as exc:
        raise SystemExit(f"backup error: {exc}") from exc
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
