"""stage_icons_to_assets.py

One-off script: copy staging PNGs from
  defect-investigation/audit/direction/symbol-final/
into
  src/breed_priority/assets/symbols/

Rules:
- 7 stat icons (str, dex, con, int, spd, cha, lck) are BLACK on transparent.
  Recolor: set R=G=B=255 wherever A>0, leave A untouched.
- The other 11 are WHITE on transparent — copy as-is.
- con.png is a Windows reserved name; it is copied as heart.png.

Run from the repo root:
    python defect-investigation/scripts/extract-symbols/stage_icons_to_assets.py
"""

import pathlib
import shutil

from PIL import Image

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
SRC_DIR   = REPO_ROOT / "defect-investigation" / "audit" / "direction" / "symbol-final"
DST_DIR   = REPO_ROOT / "src" / "breed_priority" / "assets" / "symbols"

# Stat icons that are black-on-transparent and need recoloring to white.
_BLACK_ICONS = {"str", "dex", "con", "int", "spd", "cha", "lck"}

# Windows reserved name that must be renamed on copy.
_CON_SRC_NAME = "con.png"
_CON_DST_NAME = "heart.png"


def _recolor_to_white(src_path: pathlib.Path, dst_path: pathlib.Path) -> None:
    """Load RGBA image, set R=G=B=255 wherever A>0, save to dst_path."""
    img = Image.open(src_path).convert("RGBA")
    pixels = img.load()
    width, height = img.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if a > 0:
                pixels[x, y] = (255, 255, 255, a)
    img.save(dst_path, "PNG")


def main() -> None:
    DST_DIR.mkdir(parents=True, exist_ok=True)

    copied = 0
    recolored = 0

    for src_path in sorted(SRC_DIR.glob("*.png")):
        name_tag = src_path.stem   # filename without .png

        # Determine destination filename
        if src_path.name == _CON_SRC_NAME:
            dst_name = _CON_DST_NAME
        else:
            dst_name = src_path.name

        dst_path = DST_DIR / dst_name

        if name_tag in _BLACK_ICONS:
            _recolor_to_white(src_path, dst_path)
            print(f"  [recolored] {src_path.name} -> {dst_name}")
            recolored += 1
        else:
            shutil.copy2(src_path, dst_path)
            print(f"  [copied]    {src_path.name} -> {dst_name}")
            copied += 1

    total = copied + recolored
    print(f"\nDone: {total} files total ({recolored} recolored, {copied} copied as-is)")
    print(f"Output dir: {DST_DIR}")


if __name__ == "__main__":
    main()
