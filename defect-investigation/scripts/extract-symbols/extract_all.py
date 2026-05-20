"""
Extract all bitmaps from priority SWF files and list symbol names.
Run from repo root.
"""

import os
import sys

# Add script dir to path so we can import swf_parser
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from swf_parser import parse_swf, extract_all_bitmaps

# SCRIPT_DIR = defect-investigation/scripts/extract-symbols
# DEFECT_DIR = defect-investigation/
DEFECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
SWF_DIR = os.path.join(DEFECT_DIR, "game-files", "resources", "gpak-video", "swfs")
OUTPUT_BASE = os.path.join(DEFECT_DIR, "audit", "direction", "symbol-candidates")

PRIORITY_SWFS = [
    "house.swf",
    "familytree.swf",
    "ability_icons.swf",
    "furniture.swf",
    "ui.swf",
    "catparts.swf",
    "portraits.swf",
]

NAME_TAG_KEYWORDS = [
    "str", "dex", "con", "int", "spd", "cha", "lck",
    "stimulation", "comfort", "appeal", "health", "evolution",
    "star", "circle", "triangle", "sword", "shield", "poop",
    "nametag", "name_tag", "tag", "icon", "stat",
]

def name_matches_keyword(name):
    name_lower = name.lower()
    return any(kw in name_lower for kw in NAME_TAG_KEYWORDS)


def main():
    os.makedirs(OUTPUT_BASE, exist_ok=True)

    all_interesting = []

    for swf_name in PRIORITY_SWFS:
        swf_path = os.path.join(SWF_DIR, swf_name)
        if not os.path.exists(swf_path):
            print(f"[SKIP] Not found: {swf_name}")
            continue

        out_dir = os.path.join(OUTPUT_BASE, swf_name.replace(".swf", ""))
        print(f"\n{'='*60}")
        print(f"Extracting: {swf_name}")
        print(f"  Output: {out_dir}")

        result = parse_swf(swf_path)
        names = result["names"]
        bitmaps = result["bitmaps"]

        print(f"  Bitmaps: {len(bitmaps)}, Named symbols: {len(names)}")

        # Show all named symbols
        print(f"  Named symbols:")
        for cid, name in sorted(names.items()):
            bmp_info = bitmaps.get(cid)
            bmp_marker = f" [BITMAP {bmp_info['width']}x{bmp_info['height']}]" if bmp_info else ""
            interesting = " <-- INTERESTING" if name_matches_keyword(name) else ""
            print(f"    {cid:4d} -> {name}{bmp_marker}{interesting}")

        extracted = extract_all_bitmaps(swf_path, out_dir)
        print(f"  Extracted {len(extracted)} bitmaps")

        # Show extracted with names
        for char_id, name, path, w, h in extracted:
            if name_matches_keyword(name):
                all_interesting.append({
                    "swf": swf_name,
                    "char_id": char_id,
                    "name": name,
                    "path": path,
                    "width": w,
                    "height": h,
                })
                print(f"  ** INTERESTING: {char_id:4d} {name!r} [{w}x{h}] -> {os.path.basename(path)}")

    print(f"\n{'='*60}")
    print(f"INTERESTING BITMAPS FOUND: {len(all_interesting)}")
    for item in all_interesting:
        print(f"  {item['swf']} ID={item['char_id']:4d} {item['name']!r} [{item['width']}x{item['height']}]")


if __name__ == "__main__":
    main()
