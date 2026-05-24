"""Icon extraction package for Breed Priority.

Extracts ability icons from the user's Mewgenics install — specifically the
single packed ``resources.gpak`` archive at the install root. Internally
reads the ``swfs/ability_icons.swf`` and ``swfs/ui.swf`` entries plus the
``data/abilities/*.gon`` GON files. Outputs PNGs to a per-user assets
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
