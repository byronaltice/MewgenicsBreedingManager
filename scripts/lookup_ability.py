"""Command-line utility to look up ability, passive, and disorder info.

Delegates all parsing to the app's ability metadata pipeline (abilities.py).

Usage:
    python scripts/lookup_ability.py <name>
    python scripts/lookup_ability.py --class Fighter
    python scripts/lookup_ability.py --type passive
    python scripts/lookup_ability.py --class Fighter --type active
"""
from __future__ import annotations

import argparse
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(REPO_ROOT, "src")
sys.path.insert(0, SRC_DIR)

from mewgenics.utils.config import _candidate_gpak_paths
from mewgenics.utils.abilities import (
    AbilityInfo,
    _load_ability_descriptions,
    _ABILITY_META,
    get_ability_info,
    get_abilities_by_class,
    get_abilities_by_type,
)


def _find_gpak() -> str | None:
    return next((p for p in _candidate_gpak_paths() if os.path.exists(p)), None)


def _load_meta() -> None:
    gpak_path = _find_gpak()
    if not gpak_path:
        print("ERROR: resources.gpak not found. Set MEWGENICS_GPAK_PATH env var or place it in cwd.")
        sys.exit(1)
    _, meta = _load_ability_descriptions(gpak_path)
    _ABILITY_META.clear()
    _ABILITY_META.update(meta)


def _print_info(info: AbilityInfo) -> None:
    cls = f"  Class:       {info.ability_class}" if info.ability_class else ""
    print(f"[{info.key}]  {info.display_name}  ({info.ability_type})")
    if cls:
        print(cls)
    print(f"  Description: {info.description or '(none)'}")


def main():
    parser = argparse.ArgumentParser(
        description="Look up ability, passive, and disorder info from resources.gpak."
    )
    parser.add_argument("name", nargs="?", help="Ability name to look up (e.g. slugger, Dash)")
    parser.add_argument("--class", dest="ability_class", metavar="CLASS",
                        help="Filter by class (e.g. Fighter, Collarless, Disorder)")
    parser.add_argument("--type", dest="ability_type", metavar="TYPE",
                        help="Filter by type: active, passive, disorder, basic")
    args = parser.parse_args()

    if not args.name and not args.ability_class and not args.ability_type:
        parser.print_help()
        sys.exit(1)

    _load_meta()

    if args.name:
        info = get_ability_info(args.name)
        if info is None:
            print(f"No entry found for '{args.name}'")
            sys.exit(1)
        _print_info(info)
        return

    if args.ability_class and args.ability_type:
        results = [
            i for i in get_abilities_by_class(args.ability_class)
            if i.ability_type.lower() == args.ability_type.lower()
        ]
    elif args.ability_class:
        results = get_abilities_by_class(args.ability_class)
    else:
        results = get_abilities_by_type(args.ability_type)

    if not results:
        print("No entries found.")
        sys.exit(1)

    results.sort(key=lambda i: i.display_name.lower())
    for info in results:
        _print_info(info)
        print()


if __name__ == "__main__":
    main()
