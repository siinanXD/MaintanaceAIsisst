#!/usr/bin/env python3
"""Run prompt-safe smoke checks for MongoDB Atlas Vector Search readiness."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

from app.services.atlas_health_service import (  # noqa: E402
    atlas_vector_store_health,
    load_atlas_settings,
    probe_atlas_vector_search,
)
from app.services.vector_sync_status_service import vector_store_drift_status  # noqa: E402


def main() -> int:
    """Validate Atlas configuration, health, search probe, and drift status."""
    settings = load_atlas_settings()
    missing = [
        key
        for key, value in (
            ("MONGODB_ATLAS_URI", settings["uri"]),
            ("MONGODB_ATLAS_DATABASE", settings["database"]),
            ("MONGODB_ATLAS_VECTOR_COLLECTION", settings["collection"]),
            ("MONGODB_ATLAS_VECTOR_INDEX", settings["index_name"]),
        )
        if not value
    ]
    if missing:
        print(f"Missing required settings: {', '.join(missing)}", file=sys.stderr)
        return 1

    health = atlas_vector_store_health()
    print(
        "health:",
        f"configured={health['configured']}",
        f"active={health['active']}",
        f"connected={health['connected']}",
        f"index_ready={health['index_ready']}",
        f"fallback_active={health['fallback_active']}",
        f"reason={health['reason']}",
    )
    if not health.get("ok"):
        return 1

    probe = probe_atlas_vector_search(settings=settings)
    print(
        "probe:",
        f"ok={probe['ok']}",
        f"reason={probe['reason']}",
        f"latency_ms={probe['latency_ms']}",
    )
    if not probe.get("ok"):
        return 1

    try:
        from app import create_app

        app = create_app()
        with app.app_context():
            drift = vector_store_drift_status()
    except Exception as exc:
        print(f"drift check failed: {exc.__class__.__name__}", file=sys.stderr)
        return 1

    print(
        "drift:",
        f"fallback_active={drift.get('fallback_active')}",
        f"atlas_reindex_required={drift.get('atlas_reindex_required')}",
        f"expected={drift.get('expected_vector_count')}",
        f"actual={drift.get('actual_vector_count')}",
    )
    if drift.get("fallback_active") or drift.get("atlas_reindex_required"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
