"""Tests for the background worker heartbeat used by container health checks."""

from pathlib import Path

from app.worker import heartbeat_path, process_once, write_worker_heartbeat


def test_write_worker_heartbeat_creates_timestamp_file(app, tmp_path):
    """Verify the worker writes a recent heartbeat timestamp."""
    with app.app_context():
        app.config["WORKER_HEARTBEAT_PATH"] = str(tmp_path / "worker_heartbeat")
        write_worker_heartbeat(app)

    path = Path(app.config["WORKER_HEARTBEAT_PATH"])
    assert path.exists()
    assert float(path.read_text(encoding="utf-8")) > 0


def test_process_once_writes_heartbeat_when_disabled(app, tmp_path):
    """Verify disabled workers still publish heartbeat for liveness checks."""
    with app.app_context():
        app.config["WORKER_HEARTBEAT_PATH"] = str(tmp_path / "worker_heartbeat")
        app.config["WORKER_RAG_REINDEX_ENABLED"] = False
        result = process_once(app)

    assert result["enabled"] is False
    assert heartbeat_path(app).exists()
