"""Per-user icon-assets manifest.

A small JSON file recording the extractor schema version and the source
install path. Used at startup to decide whether to re-extract.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Optional


MANIFEST_FILENAME = ".manifest.json"
MANIFEST_SCHEMA_VERSION = 2  # v2: DefineShape4 LINESTYLE2 decode fix — strokes now render


def manifest_path(icons_dir: str) -> str:
    return os.path.join(icons_dir, MANIFEST_FILENAME)


def read_manifest(icons_dir: str) -> Optional[dict]:
    path = manifest_path(icons_dir)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def is_manifest_current(icons_dir: str) -> bool:
    """True when a manifest exists at the current schema version."""
    data = read_manifest(icons_dir)
    if not data:
        return False
    try:
        return int(data.get("schema_version", 0)) == MANIFEST_SCHEMA_VERSION
    except (TypeError, ValueError):
        return False


def write_manifest(icons_dir: str, source_install_path: str) -> None:
    os.makedirs(icons_dir, exist_ok=True)
    payload = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "extracted_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_install_path": source_install_path,
    }
    with open(manifest_path(icons_dir), "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def delete_manifest(icons_dir: str) -> None:
    path = manifest_path(icons_dir)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
