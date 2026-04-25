"""
Direction 40 - Inspect GON entries for base-shape IDs 139 (eyes), 23 (eyebrows), 132 (ears).

These are the T-slot values found for Whommie (eye=139, eyebrow=23) and Bud (ear=132),
cats that carry undetected birth defects. This script checks:
  1. Raw GON block contents for each of the three IDs from resources.gpak
  2. What _VISUAL_MUT_DATA contains for those (category, id) pairs after parser loading
  3. Whether GON and parser agree on is_birth_defect for each

The key parser filter (save_parser.py line ~577):
  if slot_id < 300 and not re.search(r"\\btag\\s+birth_defect\\b", block):
      continue
IDs 139, 23, 132 are all < 300, so they are only stored if tagged birth_defect.
"""
from __future__ import annotations

import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

GPAK_PATH = ROOT / "test-saves" / "resources.gpak"
OUTPUT_PATH = ROOT / "tools" / "field_mapper" / "direction40_results.txt"

# IDs to inspect: (gon_filename_stem, slot_id, label)
TARGETS = [
    ("eyes", 139, "Whommie eye"),
    ("eyebrows", 23, "Whommie eyebrow"),
    ("ears", 132, "Bud ear"),
]


def _load_gpak_file_offsets(gpak_path: Path) -> dict[str, tuple[int, int]]:
    """Return {fname: (offset, size)} for every file in the GPAK.

    Format mirrors save_parser.py GameData.from_gpak:
      u32  count
      for each entry:  u16 name_len, utf8 name, u32 size
      data follows contiguously after directory
    """
    file_offsets: dict[str, tuple[int, int]] = {}
    with open(gpak_path, "rb") as f:
        count = struct.unpack("<I", f.read(4))[0]
        entries = []
        for _ in range(count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode("utf-8", errors="replace")
            size = struct.unpack("<I", f.read(4))[0]
            entries.append((name, size))
        dir_end = f.tell()
        offset = dir_end
        for name, size in entries:
            file_offsets[name] = (offset, size)
            offset += size
    return file_offsets


def _extract_gon_block_raw(content: str, slot_id: int) -> str | None:
    """Return the raw text of the numbered block for slot_id, or None if absent."""
    match = re.search(rf"(?<!\w){re.escape(str(slot_id))}\s*\{{", content)
    if not match:
        return None
    depth = 0
    start = content.find("{", match.start())
    if start < 0:
        return None
    pos = start
    while pos < len(content):
        ch = content[pos]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return content[start : pos + 1]
        pos += 1
    return None


def _analyse_block(block: str | None, slot_id: int) -> dict:
    """Return a summary dict for a raw GON block."""
    if block is None:
        return {
            "exists": False,
            "has_birth_defect_tag": False,
            "display_name": None,
            "stat_modifiers": [],
            "raw": None,
        }
    has_tag = bool(re.search(r"\btag\s+birth_defect\b", block))
    name_match = re.search(r"//\s*(.+)", block)
    display_name = name_match.group(1).strip() if name_match else f"Block {slot_id}"

    # Extract stat modifiers from the header (before first nested { if any)
    header = block.split("{")[1] if "{" in block else block
    # Only look at content up to the first nested block opener
    header_only = re.split(r"\{", block, maxsplit=2)[1] if block.count("{") >= 1 else block
    # Lines before the first nested {
    header_text = header_only.split("{")[0] if "{" in header_only else header_only

    stat_keys = {
        "str": "STR", "dex": "DEX", "con": "CON", "int": "INT",
        "spd": "SPD", "speed": "SPD", "cha": "CHA", "lck": "LCK", "blind": "blind",
    }
    stats_found = []
    seen_labels: set[str] = set()
    for key, label in stat_keys.items():
        if label in seen_labels:
            continue
        m = re.search(rf"(?<!\w){re.escape(key)}\s+(-?\d+)", block)
        if m:
            val = int(m.group(1))
            stats_found.append(f"{'+' if val >= 0 else ''}{val} {label}")
            seen_labels.add(label)

    return {
        "exists": True,
        "has_birth_defect_tag": has_tag,
        "display_name": display_name,
        "stat_modifiers": stats_found,
        "raw": block,
    }


def main():
    lines: list[str] = ["Direction 40 Results", "=" * 60, ""]

    if not GPAK_PATH.exists():
        lines.append(f"ERROR: resources.gpak not found at {GPAK_PATH}")
        OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
        print("\n".join(lines))
        return

    lines.append(f"GPAK: {GPAK_PATH}")
    lines.append("")

    # --- Load GPAK file table ---
    file_offsets = _load_gpak_file_offsets(GPAK_PATH)

    # Find all mutation GON files and note their keys
    mut_gon_files = {k: v for k, v in file_offsets.items()
                     if k.startswith("data/mutations/") and k.endswith(".gon")}
    lines.append("Mutation GON files in GPAK:")
    for fname in sorted(mut_gon_files):
        lines.append(f"  {fname}")
    lines.append("")

    # --- Load raw GON content for categories we need ---
    cat_gon_content: dict[str, str] = {}
    with open(GPAK_PATH, "rb") as f:
        for fname, (foff, fsz) in mut_gon_files.items():
            category = fname.split("/")[-1].replace(".gon", "")
            f.seek(foff)
            cat_gon_content[category] = f.read(fsz).decode("utf-8", errors="replace")

    # --- Check 1: Raw GON block inspection ---
    lines.append("=" * 60)
    lines.append("CHECK 1: Raw GON block contents")
    lines.append("=" * 60)
    lines.append("")

    gon_results: dict[tuple[str, int], dict] = {}
    for (category, slot_id, label) in TARGETS:
        content = cat_gon_content.get(category)
        if content is None:
            info = {
                "exists": False, "has_birth_defect_tag": False,
                "display_name": None, "stat_modifiers": [], "raw": None,
                "category_found": False,
            }
        else:
            info = _analyse_block(_extract_gon_block_raw(content, slot_id), slot_id)
            info["category_found"] = True
        gon_results[(category, slot_id)] = info

        lines.append(f"Target: {label} — category='{category}', id={slot_id}")
        if not info.get("category_found", True):
            lines.append(f"  GON FILE: NOT FOUND (no data/mutations/{category}.gon in GPAK)")
        elif not info["exists"]:
            lines.append(f"  BLOCK {slot_id}: NOT FOUND in {category}.gon")
        else:
            lines.append(f"  BLOCK EXISTS: yes")
            lines.append(f"  tag birth_defect: {info['has_birth_defect_tag']}")
            lines.append(f"  Display name: {info['display_name']}")
            lines.append(f"  Stat modifiers: {info['stat_modifiers'] or '(none)'}")
            lines.append(f"  Raw block (first 300 chars): {info['raw'][:300] if info['raw'] else 'N/A'}")
        lines.append("")

    # --- Check 2: Parser lookup via _VISUAL_MUT_DATA ---
    lines.append("=" * 60)
    lines.append("CHECK 2: Parser _VISUAL_MUT_DATA lookup")
    lines.append("=" * 60)
    lines.append("")

    # Load GameData directly (same as the app does)
    from save_parser import GameData, _VISUAL_MUT_DATA as parser_vmd_before

    game_data = GameData.from_gpak(str(GPAK_PATH))
    vmd = game_data.visual_mutation_data

    lines.append(f"_VISUAL_MUT_DATA categories after loading: {sorted(vmd.keys())}")
    lines.append("")

    parser_results: dict[tuple[str, int], tuple | None] = {}
    for (category, slot_id, label) in TARGETS:
        cat_data = vmd.get(category, {})
        entry = cat_data.get(slot_id)
        parser_results[(category, slot_id)] = entry

        lines.append(f"Target: {label} — category='{category}', id={slot_id}")
        if entry is None:
            lines.append(f"  LOOKUP: NOT IN _VISUAL_MUT_DATA")
            # Also check if the category key even exists
            if category not in vmd:
                lines.append(f"  (category '{category}' not a key in _VISUAL_MUT_DATA)")
                # Try to find the right key
                candidates = [k for k in vmd if category.rstrip("s") in k or k in category]
                if candidates:
                    lines.append(f"  Possible matching keys: {candidates}")
                    for cand in candidates:
                        alt_entry = vmd[cand].get(slot_id)
                        lines.append(f"    '{cand}' -> id={slot_id}: {alt_entry}")
        else:
            display_name, stat_desc, is_birth_defect = entry
            lines.append(f"  display_name: {display_name}")
            lines.append(f"  stat_desc: {stat_desc}")
            lines.append(f"  is_birth_defect: {is_birth_defect}")
        lines.append("")

    # --- Check 3: Cross-reference ---
    lines.append("=" * 60)
    lines.append("CHECK 3: Cross-reference GON vs parser")
    lines.append("=" * 60)
    lines.append("")

    all_agree = True
    for (category, slot_id, label) in TARGETS:
        gon_info = gon_results[(category, slot_id)]
        parser_entry = parser_results[(category, slot_id)]

        gon_tagged = gon_info.get("has_birth_defect_tag", False)
        parser_tagged = parser_entry[2] if parser_entry else None

        lines.append(f"{label} ('{category}', id={slot_id}):")
        lines.append(f"  GON tag birth_defect: {gon_tagged}")
        lines.append(f"  Parser is_birth_defect: {parser_tagged}")

        if gon_tagged and parser_tagged is False:
            lines.append("  *** DISAGREEMENT: GON tags birth_defect but parser says False ***")
            all_agree = False
        elif gon_tagged and parser_entry is None:
            lines.append("  *** DISAGREEMENT: GON tags birth_defect but parser has NO ENTRY ***")
            all_agree = False
        elif not gon_tagged and parser_tagged:
            lines.append("  *** DISAGREEMENT: GON NOT tagged but parser says is_birth_defect=True ***")
            all_agree = False
        elif not gon_tagged and parser_entry is None:
            lines.append("  AGREE: GON not tagged birth_defect, parser skips this base-shape ID (correct)")
        elif gon_tagged and parser_tagged:
            lines.append("  AGREE: both say birth_defect=True")
        else:
            lines.append(f"  Status: GON_tag={gon_tagged}, parser_entry={parser_entry}")
        lines.append("")

    # --- Summary verdict ---
    lines.append("=" * 60)
    lines.append("VERDICT")
    lines.append("=" * 60)
    lines.append("")

    any_gon_tagged = any(
        gon_results[(cat, sid)].get("has_birth_defect_tag", False)
        for cat, sid, _ in TARGETS
    )

    if any_gon_tagged:
        lines.append("At least one GON entry IS tagged birth_defect.")
        if not all_agree:
            lines.append("Parser DISAGREES with GON: bug is in lookup logic (parser misses tagged data).")
        else:
            lines.append("Parser AGREES with GON: lookup logic is correct.")
    else:
        lines.append("NONE of the three GON entries (ids 139, 23, 132) are tagged birth_defect.")
        lines.append("These are clean base shapes. The defect source is NOT in these GON blocks.")
        lines.append("The undetected birth defects must come from a source other than the T-slot GON entries.")
        lines.append("")
        lines.append("Recommended next step:")
        lines.append("  Audit the 10 pre-corridor ability strings (+0x7d0..+0x8f0) across all cats.")
        lines.append("  Compare Whommie/Bud tokens vs controls (Kami, Petronij, Murisha) for any token")
        lines.append("  that appears only in defect-positive cats and survives/fails parser filtering.")
        lines.append("  See CLAUDE.md 'Best Path Forward' step 1.")

    result_text = "\n".join(lines)
    OUTPUT_PATH.write_text(result_text, encoding="utf-8")
    print(result_text)
    print(f"\nResults written to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
