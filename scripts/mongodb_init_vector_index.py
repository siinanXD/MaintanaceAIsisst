#!/usr/bin/env python3
"""Ensure the MongoDB Atlas Vector Search index exists for knowledge retrieval."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")


def main() -> int:
    """Create the configured vector index when missing."""
    from app.services.atlas_health_service import (
        ensure_atlas_vector_index,
        load_atlas_settings,
    )

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

    result = ensure_atlas_vector_index(settings=settings)
    status = result.get("status")
    if status == "ready":
        print(f"Atlas vector index ready: {result.get('index_name')}")
        return 0
    if status == "created":
        print(f"Atlas vector index created: {result.get('index_name')}")
        return 0
    print(f"Atlas vector index setup failed: {result.get('reason', 'unknown')}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
