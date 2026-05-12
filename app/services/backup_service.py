"""Backup and restore services for database and file storage."""

import json
import shutil
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from flask import current_app
from sqlalchemy.engine.url import make_url

from app.extensions import db

BACKUP_VERSION = 1
MANIFEST_NAME = "manifest.json"
BACKUP_PREFIX = "maintenance_backup_"


def create_backup(actor=None, reason="manual"):
    """Create a ZIP backup for the SQLite database and configured file folders."""
    backup_folder = _backup_folder()
    backup_folder.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
    backup_path = backup_folder / f"{BACKUP_PREFIX}{timestamp}.zip"
    manifest = {
        "version": BACKUP_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "created_by": getattr(actor, "username", None),
        "reason": reason,
        "database": None,
        "folders": [],
    }

    database_path = sqlite_database_path()
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        if database_path and database_path.exists():
            db.session.remove()
            archive.write(database_path, "database/maintenance.db")
            manifest["database"] = "database/maintenance.db"
        for key, config_name in (
            ("uploads", "UPLOAD_FOLDER"),
            ("documents", "DOCUMENTS_FOLDER"),
            ("logs", "LOG_DIR"),
        ):
            folder_config = current_app.config.get(config_name)
            if not folder_config:
                continue
            folder = Path(folder_config).resolve()
            if not folder.exists():
                continue
            _write_folder(archive, folder, key)
            manifest["folders"].append({"name": key, "config": config_name})
        archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
    return backup_metadata(backup_path)


def list_backups():
    """Return known backup files sorted newest first."""
    folder = _backup_folder()
    if not folder.exists():
        return []
    backups = [backup_metadata(path) for path in folder.glob(f"{BACKUP_PREFIX}*.zip")]
    return sorted(backups, key=lambda item: item["created_at"], reverse=True)


def backup_path_for(backup_id):
    """Return a safe backup path for a public backup id."""
    safe_name = Path(str(backup_id or "")).name
    if not safe_name.endswith(".zip") or not safe_name.startswith(BACKUP_PREFIX):
        return None
    path = (_backup_folder() / safe_name).resolve()
    backup_folder = _backup_folder().resolve()
    if backup_folder not in path.parents:
        return None
    return path if path.exists() else None


def restore_backup(backup_id, actor=None, confirm=False):
    """Restore a validated backup ZIP after creating a safety backup."""
    if not confirm:
        return None, {"error": "Restore requires confirm=true"}, 400
    source_path = backup_path_for(backup_id)
    if not source_path:
        return None, {"error": "Backup not found"}, 404
    try:
        with zipfile.ZipFile(source_path) as archive:
            manifest = _validated_manifest(archive)
            create_backup(actor=actor, reason=f"pre_restore:{source_path.name}")
            with TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir)
                archive.extractall(tmp_path)
                _restore_database(tmp_path, manifest)
                _restore_folders(tmp_path, manifest)
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        return None, {"error": str(exc)}, 400
    return {"restored_backup": source_path.name}, None, 200


def backup_metadata(path):
    """Return public metadata for one backup ZIP."""
    stat = path.stat()
    created_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
    return {
        "id": path.name,
        "filename": path.name,
        "size_bytes": stat.st_size,
        "created_at": created_at,
        "download_url": f"/api/v1/admin/backups/{path.name}/download",
    }


def sqlite_database_path():
    """Return the configured SQLite database file path, or None for non-file DBs."""
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI", "")
    url = make_url(uri)
    if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def _backup_folder():
    """Return the configured backup folder path."""
    return Path(current_app.config["BACKUP_FOLDER"]).resolve()


def _write_folder(archive, folder, archive_prefix):
    """Write a folder recursively into the backup archive."""
    for path in folder.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(folder).as_posix()
        archive.write(path, f"{archive_prefix}/{relative}")


def _validated_manifest(archive):
    """Return a validated backup manifest and reject unsafe paths."""
    names = set(archive.namelist())
    if MANIFEST_NAME not in names:
        raise ValueError("Backup manifest missing")
    manifest = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
    if manifest.get("version") != BACKUP_VERSION:
        raise ValueError("Unsupported backup version")
    for name in names:
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Backup contains unsafe paths")
    return manifest


def _restore_database(extracted_path, manifest):
    """Restore the SQLite database file from an extracted backup."""
    database_member = manifest.get("database")
    target = sqlite_database_path()
    if not database_member or not target:
        return
    source = (extracted_path / database_member).resolve()
    if not source.exists():
        raise ValueError("Backup database file missing")
    target.parent.mkdir(parents=True, exist_ok=True)
    db.session.remove()
    shutil.copy2(source, target)


def _restore_folders(extracted_path, manifest):
    """Restore configured file folders from an extracted backup."""
    for folder_info in manifest.get("folders", []):
        source = (extracted_path / folder_info["name"]).resolve()
        target = Path(current_app.config[folder_info["config"]]).resolve()
        if not source.exists():
            continue
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target)
