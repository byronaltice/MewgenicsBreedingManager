"""
Explore SWF files and list all tags/symbols to understand the structure.
Usage: python explore_swf.py <swf_file>
"""

import sys
import os

try:
    from swf.reader import SWFReader
    from swf.movie import SWF
except ImportError:
    print("pyswf not found. Install with: pip install pyswf")
    sys.exit(1)


def explore_swf(swf_path):
    print(f"\n{'='*60}")
    print(f"SWF: {os.path.basename(swf_path)}")
    print(f"{'='*60}")

    with open(swf_path, "rb") as f:
        swf = SWF(f)

    print(f"Version: {swf.header.version}")
    print(f"Tags found: {len(swf.tags)}")

    tag_type_counts = {}
    for tag in swf.tags:
        tag_name = type(tag).__name__
        tag_type_counts[tag_name] = tag_type_counts.get(tag_name, 0) + 1

    print("\nTag type summary:")
    for tag_name, count in sorted(tag_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {tag_name}: {count}")

    # Look for named symbols (SymbolClass, ExportAssets)
    print("\nNamed symbols:")
    for tag in swf.tags:
        tag_class = type(tag).__name__
        if tag_class in ("SWFSymbolClassTag", "SWFExportAssetsTag"):
            if hasattr(tag, "symbols"):
                for sym in tag.symbols:
                    print(f"  ID {sym.id:4d} -> {sym.name}")

    # List image-like tags
    print("\nImage tags (bitmaps):")
    image_tag_types = (
        "SWFDefineBitsLossless2Tag",
        "SWFDefineBitsLosslessTag",
        "SWFDefineBitsJPEG2Tag",
        "SWFDefineBitsJPEG3Tag",
        "SWFDefineBitsJPEG4Tag",
        "SWFDefineBitsTag",
    )
    for tag in swf.tags:
        tag_class = type(tag).__name__
        if tag_class in image_tag_types:
            char_id = getattr(tag, "characterId", getattr(tag, "character_id", "?"))
            print(f"  {tag_class} ID={char_id}")


if __name__ == "__main__":
    swf_dir = "C:/Users/Byron/gitprojects/MewgenicsBreedingManager/defect-investigation/game-files/resources/gpak-video/swfs"

    if len(sys.argv) > 1:
        targets = sys.argv[1:]
    else:
        targets = ["house.swf", "familytree.swf", "ability_icons.swf", "furniture.swf", "ui.swf"]

    for swf_name in targets:
        swf_path = os.path.join(swf_dir, swf_name)
        if os.path.exists(swf_path):
            explore_swf(swf_path)
        else:
            print(f"Not found: {swf_path}")
