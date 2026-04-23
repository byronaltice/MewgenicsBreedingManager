"""Direction #16 -- properties table exploration.

The save has 259 rows in the `properties` table (key TEXT, value INTEGER).
These are world-state values and haven't been examined. This script:

1. Dumps all 259 key/value pairs to see if any are cat-specific.
2. Searches for known cat db_keys or UIDs as values.
3. Looks for any keys that look like defect/mutation/variant identifiers.
"""
from __future__ import annotations

import re
import sqlite3
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "test-saves").exists():
    ROOT = ROOT.parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction16_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def main() -> None:
    out("=" * 70)
    out("Direction #16 -- properties table dump")
    out("=" * 70)
    out(f"Save: {SAVE}\n")

    conn = sqlite3.connect(str(SAVE))

    rows = conn.execute("SELECT key, data FROM properties ORDER BY key").fetchall()
    out(f"Total rows: {len(rows)}\n")

    out("-- All key/value pairs --")
    for key, value in rows:
        out(f"  {key!r:50s} = {value}")
    out("")

    out("-- Keys containing cat/defect/mutation/variant keywords --")
    keywords = re.compile(r"(cat|defect|mutation|variant|birth|part|body|eye|ear|brow|fur|leg|arm|tail|head|mouth)", re.IGNORECASE)
    for key, value in rows:
        if keywords.search(str(key)):
            out(f"  {key!r:50s} = {value}")
    out("")

    out("-- Searching for known cat db_keys as property values --")
    save_data = parse_save(str(SAVE))
    cat_by_key = {c.db_key: c for c in save_data.cats}
    target_keys = [853, 887, 840, 841, 68]  # Whommie, Bud, Kami, Petronij, Flekpus
    prop_values = {value for _, value in rows}
    for db_key in target_keys:
        cat = cat_by_key.get(db_key)
        name = cat.name if cat else "?"
        found = db_key in prop_values
        out(f"  db_key={db_key} ({name}): {'FOUND in property values' if found else 'not found'}")
    out("")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
