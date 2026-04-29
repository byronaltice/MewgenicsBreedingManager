"""Audit a Mewgenics save for cats with undetected SWF-anchor-absence birth defects.

This is a standalone diagnostic.  It does NOT modify the save.  It tells
you which cats in the save would have birth defects that a naive parser
would miss — the bug described in MISSING_BIRTH_DEFECTS_REPORT.md.

Usage:
    python3 audit_missing_birth_defects.py [<save.sav>] --gpak <resources.gpak>

If no save path is given, ./example_save.sav is used.

Dependencies:
    - Python 3.10+
    - lz4 (`pip install lz4`)
    - swf_anchor_walker.py (bundled in the same directory)
"""
from __future__ import annotations

import argparse
import sqlite3
import struct
import sys
from pathlib import Path

import lz4.block

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from swf_anchor_walker import (
    ANCHOR_NAMES,
    CAT_HEAD_PLACEMENTS_CHAR_ID,
    parse_cat_head_placements,
)


# Anchor name -> (display label, optional eyebrow propagation label).
ANCHOR_REPORT_INFO: dict[str, tuple[str, str | None]] = {
    "leye":  ("Left Eye",  "Left Eyebrow"),
    "reye":  ("Right Eye", "Right Eyebrow"),
    "lear":  ("Left Ear",  None),
    "rear":  ("Right Ear", None),
    "mouth": ("Mouth",     None),
    # ahead, aneck, aface have no visible part slot; reported as a footnote only.
}


# ── minimal blob reader ───────────────────────────────────────────────────────
#
# A Mewgenics save is a SQLite database; the `cats` table holds one
# LZ4-compressed blob per cat.  Each blob's variable-length header contains
# (in order): breed_id (u32), uid (u64), name (utf-16 with u64 char-count
# prefix), name_tag (utf-8 with u64 byte-count prefix), two parent UIDs
# (u64 each), collar (utf-8 length-prefixed), one u32, then 64 skipped
# bytes, then a 72-element u32 array (the "T array").  T[8] is the cat's
# headShape — the only field this audit needs beyond the cat name.
#
# The string readers are tolerant: if a length looks bogus (>10000), they
# treat the field as absent and don't advance, matching the main parser's
# BinaryReader.str() behavior.

_STR_LEN_SANITY_LIMIT = 10_000


def _read_u32(buf: bytes, pos: int) -> tuple[int, int]:
    return struct.unpack_from("<I", buf, pos)[0], pos + 4


def _read_u64(buf: bytes, pos: int) -> tuple[int, int]:
    return struct.unpack_from("<Q", buf, pos)[0], pos + 8


def _read_utf16_str(buf: bytes, pos: int) -> tuple[str, int]:
    char_count, after_len = _read_u64(buf, pos)
    byte_count = int(char_count) * 2
    if byte_count < 0 or after_len + byte_count > len(buf):
        return "", pos
    raw = buf[after_len:after_len + byte_count]
    return raw.decode("utf-16-le", errors="ignore"), after_len + byte_count


def _read_utf8_str(buf: bytes, pos: int) -> tuple[str, int]:
    byte_count, after_len = _read_u64(buf, pos)
    if byte_count < 0 or byte_count > _STR_LEN_SANITY_LIMIT:
        return "", pos  # treat as absent, don't advance — matches main parser
    if after_len + byte_count > len(buf):
        return "", pos
    raw = buf[after_len:after_len + int(byte_count)]
    return raw.decode("utf-8", errors="ignore"), after_len + int(byte_count)


def _parse_cat_minimal(blob: bytes) -> tuple[str, int] | None:
    """Decompress a cat blob and extract (name, headShape).  None on failure."""
    try:
        uncompressed_size = struct.unpack("<I", blob[:4])[0]
        raw = lz4.block.decompress(blob[4:], uncompressed_size=uncompressed_size)
        pos = 0
        _, pos = _read_u32(raw, pos)        # breed_id
        _, pos = _read_u64(raw, pos)        # uid
        name, pos = _read_utf16_str(raw, pos)
        _, pos = _read_utf8_str(raw, pos)   # name_tag (may be empty)
        _, pos = _read_u64(raw, pos)        # parent uid a
        _, pos = _read_u64(raw, pos)        # parent uid b
        _, pos = _read_utf8_str(raw, pos)   # collar (may be empty)
        _, pos = _read_u32(raw, pos)
        pos += 64                           # padding/header tail
        # T[0..71] follow.  T[8] = headShape.
        head_shape = struct.unpack_from("<I", raw, pos + 8 * 4)[0]
        return name, head_shape
    except Exception:
        return None


def load_cats(save_path: Path) -> list[tuple[int, str, int]]:
    conn = sqlite3.connect(f"file:{save_path}?mode=ro", uri=True)
    rows = conn.execute("SELECT key, data FROM cats").fetchall()
    conn.close()
    cats: list[tuple[int, str, int]] = []
    for key, blob in rows:
        parsed = _parse_cat_minimal(blob)
        if parsed is None:
            continue
        name, head_shape = parsed
        cats.append((key, name, head_shape))
    return cats


# ── SWF extraction from gpak ──────────────────────────────────────────────────
#
# resources.gpak is a flat container: u32 file count, then for each entry a
# u16-prefixed UTF-8 name and a u32 size; the file blobs follow contiguously
# after the directory, in directory order.

def load_swf_anchors(gpak_path: Path) -> list[frozenset[str]]:
    with open(gpak_path, "rb") as f:
        count = struct.unpack("<I", f.read(4))[0]
        entries: list[tuple[str, int]] = []
        for _ in range(count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode("utf-8", errors="replace")
            size = struct.unpack("<I", f.read(4))[0]
            entries.append((name, size))
        offset = f.tell()
        offsets: dict[str, tuple[int, int]] = {}
        for name, size in entries:
            offsets[name] = (offset, size)
            offset += size

        swf_key = next(
            (k for k in offsets if k.endswith(".swf") and "catpart" in k.lower()),
            None,
        )
        if swf_key is None:
            return []
        foff, fsz = offsets[swf_key]
        f.seek(foff)
        return parse_cat_head_placements(f.read(fsz))


# ── audit ─────────────────────────────────────────────────────────────────────

def audit(save_path: Path, gpak_path: Path) -> int:
    per_frame = load_swf_anchors(gpak_path)
    if not per_frame:
        print(
            f"ERROR: could not extract char_id={CAT_HEAD_PLACEMENTS_CHAR_ID} "
            f"from {gpak_path}",
            file=sys.stderr,
        )
        return 1

    cats = load_cats(save_path)
    print(f"Save        : {save_path}")
    print(f"GPAK        : {gpak_path}")
    print(f"SWF frames  : {len(per_frame)}")
    print(f"Cats parsed : {len(cats)}")
    print()

    affected: list[tuple[int, str, int, frozenset[str]]] = []
    for db_key, name, head_shape in cats:
        target = head_shape - 1
        if target < 0 or target >= len(per_frame):
            continue
        missing = ANCHOR_NAMES - per_frame[target]
        if missing & set(ANCHOR_REPORT_INFO):
            affected.append((db_key, name, head_shape, missing))

    if not affected:
        print("No cats affected by the SWF-anchor-absence class of defects.")
        return 0

    print(f"Cats affected by SWF-anchor-absence defects: {len(affected)}")
    print()
    print(f"{'db_key':>6}  {'name':<24}  {'headShape':>9}  predicted defects")
    print("-" * 96)
    for db_key, name, head_shape, missing in affected:
        labels: list[str] = []
        for anchor in sorted(missing):
            info = ANCHOR_REPORT_INFO.get(anchor)
            if info is None:
                continue
            slot_label, eyebrow_label = info
            labels.append(f"{slot_label} Birth Defect")
            if eyebrow_label is not None:
                labels.append(f"{eyebrow_label} Birth Defect")
        non_visible = sorted(missing - set(ANCHOR_REPORT_INFO))
        suffix = f"  [also missing non-visible anchors: {', '.join(non_visible)}]" if non_visible else ""
        print(f"{db_key:>6}  {name:<24}  {head_shape:>9}  {', '.join(labels)}{suffix}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "save",
        nargs="?",
        default=str(HERE / "example_save.sav"),
        help="path to a Mewgenics .sav file (default: ./example_save.sav)",
    )
    parser.add_argument(
        "--gpak",
        required=True,
        help="path to resources.gpak from your Mewgenics install",
    )
    args = parser.parse_args()

    save_path = Path(args.save)
    gpak_path = Path(args.gpak)
    if not save_path.exists():
        print(f"ERROR: save not found: {save_path}", file=sys.stderr)
        sys.exit(1)
    if not gpak_path.exists():
        print(f"ERROR: gpak not found: {gpak_path}", file=sys.stderr)
        sys.exit(1)

    sys.exit(audit(save_path, gpak_path))


if __name__ == "__main__":
    main()
