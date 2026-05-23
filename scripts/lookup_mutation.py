"""Command-line utility to look up a visual mutation title and description.

Delegates all parsing to the app's GameData pipeline (save_parser.py).

Usage:
    python scripts/lookup_mutation.py body 300
    python scripts/lookup_mutation.py body -s 304 -e 309
"""
from __future__ import annotations

import argparse
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from save_parser import GameData
from mewgenics.utils.config import _candidate_gpak_paths


def _find_gpak() -> str | None:
    return next((p for p in _candidate_gpak_paths() if os.path.exists(p)), None)


def _load_slot_data(slot: str) -> dict[int, tuple[str, str, bool]]:
    gpak_path = _find_gpak()
    if not gpak_path:
        print("ERROR: resources.gpak not found. Set MEWGENICS_GPAK_PATH env var or place it next to the script.")
        sys.exit(1)
    return GameData.from_gpak(gpak_path).visual_mutation_data.get(slot, {})


def _print_entry(mutation_id: int, slot_data: dict[int, tuple[str, str, bool]]) -> bool:
    entry = slot_data.get(mutation_id)
    if entry is None:
        return False
    name, stat_desc, _is_defect = entry
    print(f"[{mutation_id}] {name}  —  {stat_desc or '(no description)'}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Look up visual mutation title and description from resources.gpak."
    )
    parser.add_argument("slot", help="Mutation slot (e.g. body, head, tail)")
    parser.add_argument("id", nargs="?", type=int, help="Single mutation ID")
    parser.add_argument("-s", "--start", type=int, help="Start of ID range (inclusive)")
    parser.add_argument("-e", "--end", type=int, help="End of ID range (inclusive)")
    args = parser.parse_args()

    slot = args.slot.lower()

    if args.start is not None or args.end is not None:
        if args.start is None or args.end is None:
            parser.error("-s/--start and -e/--end must both be specified for a range lookup")
        slot_data = _load_slot_data(slot)
        found = 0
        for mutation_id in range(args.start, args.end + 1):
            if _print_entry(mutation_id, slot_data):
                found += 1
        if found == 0:
            print(f"No entries found for slot='{slot}' in range {args.start}–{args.end}")
    elif args.id is not None:
        slot_data = _load_slot_data(slot)
        if not _print_entry(args.id, slot_data):
            print(f"No entry found for slot='{slot}' id={args.id}")
            sys.exit(1)
    else:
        parser.error("Provide a single ID or use -s/--start and -e/--end for a range")


if __name__ == "__main__":
    main()
