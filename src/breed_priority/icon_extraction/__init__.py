"""Icon extraction package for Breed Priority.

Extracts ability icons from the user's Mewgenics install (SWF files under
``resources/gpak-video/swfs/``) and the GON metadata under
``resources/gpak-text/data/abilities/``. Outputs PNGs to a per-user assets
directory; no game-derived assets are committed to the repo.

Public entry points:
    extract_abilities.extract_ability_icons(install_path, assets_dir, ...)
    gon_ability_map.build_ability_icon_map(install_path, assets_dir)
    write_manifest(assets_dir, install_path)
"""

from .manifest import (
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_VERSION,
    is_manifest_current,
    read_manifest,
    write_manifest,
)

__all__ = [
    "MANIFEST_FILENAME",
    "MANIFEST_SCHEMA_VERSION",
    "is_manifest_current",
    "read_manifest",
    "write_manifest",
]
