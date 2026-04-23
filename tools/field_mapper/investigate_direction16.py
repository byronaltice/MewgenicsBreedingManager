"""Direction #16 -- Explore the properties table for cat-specific keys.

The save's `properties` table stores integer world-state flags keyed by text.
This script inventories the keys and checks whether any property names look
cat-specific (db_key/uid/name encoded into the key), which would make the table
relevant to the missing birth-defect investigation.
"""
from __future__ import annotations

import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction16_results.txt"

TARGET_NAMES = ("Whommie", "Bud", "Kami", "Petronij", "Romanoba", "Murisha")
CAMEL_SPLIT_RE = re.compile(r"(?<!^)(?=[A-Z])")
DIGIT_RE = re.compile(r"\d+")
DBKEY_WINDOW = 2
TOP_PREFIXES = 20
TOP_DIGITS = 20

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def key_prefix(key: str) -> str:
    if "_" in key:
        return key.split("_", 1)[0]
    camel_parts = CAMEL_SPLIT_RE.split(key)
    return camel_parts[0] if camel_parts else key


def main() -> None:
    out("=" * 70)
    out("Direction #16 -- Properties table exploration")
    out("=" * 70)
    out(f"Save: {SAVE}")
    out()

    save_data = parse_save(str(SAVE))
    cat_map = {cat.name: cat for cat in save_data.cats}
    target_db_keys = {cat_map[name].db_key for name in TARGET_NAMES if name in cat_map}
    target_uids = {str(cat_map[name]._uid_int) for name in TARGET_NAMES if name in cat_map}
    target_names_lower = {name.lower() for name in TARGET_NAMES}

    conn = sqlite3.connect(str(SAVE))
    rows = conn.execute("SELECT key, data FROM properties ORDER BY key").fetchall()
    conn.close()

    out(f"Total properties rows: {len(rows)}")
    out()

    prefix_counter: Counter[str] = Counter()
    digit_counter: Counter[str] = Counter()
    prefix_examples: dict[str, list[str]] = defaultdict(list)
    suspicious_rows: list[tuple[str, int, str]] = []

    for key, value in rows:
        prefix = key_prefix(key)
        prefix_counter[prefix] += 1
        if len(prefix_examples[prefix]) < 5:
            prefix_examples[prefix].append(key)

        for match in DIGIT_RE.findall(key):
            digit_counter[match] += 1

        lower_key = key.lower()
        reason_parts: list[str] = []

        if any(name in lower_key for name in target_names_lower):
            reason_parts.append("contains target cat name")
        if any(uid in key for uid in target_uids):
            reason_parts.append("contains target uid digits")

        digit_matches = DIGIT_RE.findall(key)
        for digits in digit_matches:
            number = int(digits)
            if number in target_db_keys:
                reason_parts.append(f"contains target db_key {number}")
            elif any(abs(number - db_key) <= DBKEY_WINDOW for db_key in target_db_keys):
                reason_parts.append(f"near target db_key {number}")

        if reason_parts:
            suspicious_rows.append((key, value, "; ".join(reason_parts)))

    out("Top key prefixes:")
    for prefix, count in prefix_counter.most_common(TOP_PREFIXES):
        out(f"  {prefix:24s} count={count:3d} examples={prefix_examples[prefix]}")
    out()

    out("Most common digit substrings in property keys:")
    for digits, count in digit_counter.most_common(TOP_DIGITS):
        out(f"  {digits:12s} count={count:3d}")
    out()

    out("Rows whose keys look cat-specific:")
    if suspicious_rows:
        for key, value, reason in suspicious_rows:
            out(f"  {key:50s} value={value:<8d} reason={reason}")
    else:
        out("  (none)")
    out()

    out("Sample full property listing (first 80 sorted keys):")
    for key, value in rows[:80]:
        out(f"  {key:50s} {value}")
    out()

    out("Verdict:")
    if suspicious_rows:
        out("  At least one property key looks cat-specific; properties table remains a possible lead.")
    else:
        out("  No property keys mention target cat names, target UIDs, or target db_keys. The table appears to hold only global/world-state integers, not per-cat defect flags.")

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
