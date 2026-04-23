"""Direction #20 -- Inspect the TypeScript editor write path.

Fetch the public community editor source and answer the remaining question from
Direction 4a: does its mutation write path encode anything beyond the same
structured mutation table (our T array), especially for "No Part" defects?
"""
from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "direction20_results.txt"

FILES = {
    "patch_mutations": "https://raw.githubusercontent.com/michael-trinity/mewgenics-savegame-editor/refs/heads/main/app/utils/patch/mutations.ts",
    "mutation_editor": "https://raw.githubusercontent.com/michael-trinity/mewgenics-savegame-editor/refs/heads/main/app/components/editor/MutationEditor.vue",
    "parse_mutations": "https://raw.githubusercontent.com/michael-trinity/mewgenics-savegame-editor/refs/heads/main/app/utils/parse/mutations.ts",
}

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def fetch(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8", errors="replace")


def grab(text: str, pattern: str) -> str:
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    return match.group(0).strip() if match else "(not found)"


def main() -> None:
    out("=" * 70)
    out("Direction #20 -- TypeScript editor write-path audit")
    out("=" * 70)

    contents = {name: fetch(url) for name, url in FILES.items()}

    patch_mutations = contents["patch_mutations"]
    mutation_editor = contents["mutation_editor"]
    parse_mutations = contents["parse_mutations"]

    out("Sources fetched:")
    for name, url in FILES.items():
        out(f"  {name}: {url}")
    out()

    out("=" * 70)
    out("patch/mutations.ts")
    out("=" * 70)
    out(grab(patch_mutations, r"export function patchMutCoat[\s\S]*?return out\s*\n\s*}"))
    out()
    out(grab(patch_mutations, r"export function patchMutSlot[\s\S]*?return out\s*\n\s*}"))
    out()

    out("=" * 70)
    out("MutationEditor.vue write calls")
    out("=" * 70)
    for pattern in (
        r"function applyMutation[\s\S]*?cancelEdit\(\)\s*\n}",
        r"function clearSlot[\s\S]*?\n}",
        r"function mirrorSlot[\s\S]*?\n}",
        r"let entries = \[\.\.\.catMap\.entries\(\)\]\.filter\(\(\[id\]\) => Number\(id\) >= 300\)",
        r"function getEntry\(category: string, id: number\): MutationEntry \| null \{\s*if \(!mutationsDB\.value \|\| id < 300\) return null",
    ):
        out(grab(mutation_editor, pattern))
        out()

    out("=" * 70)
    out("parse/mutations.ts table framing")
    out("=" * 70)
    out(grab(parse_mutations, r"const MUT_TABLE_SIZE = 16 \+ 14 \* 20[\s\S]*?return bestOff\s*\}"))
    out()

    out("=" * 70)
    out("Findings")
    out("=" * 70)
    out("1. `patchMutSlot()` writes exactly one `u32` at `baseOff + 16 + (slotIdx - 1) * 20`.")
    out("   It does not write any companion flag, variant bit, or second structure.")
    out("2. `patchMutCoat()` only writes the coat `u32` at `baseOff + 4` and propagates the coat echo to slot entries at `+4` within each 20-byte record.")
    out("3. `MutationEditor.vue` passes a single `newId` into `patchMutSlot()` for apply/mirror/clear operations.")
    out("   `clearSlot()` writes `0`; `mirrorSlot()` copies the other slot's current `slotId`; no extra write happens.")
    out("4. The browser only exposes mutation IDs `>= 300` (`Number(id) >= 300`), and `getEntry()` returns null for IDs `< 300`.")
    out("   That means the editor UI does not even browse explicit low-ID birth defects such as `2`, nor any special `0xFFFFFFFE` sentinel.")
    out("5. The parser side in this editor still frames the same `16 + 14 * 20` byte mutation table we already mapped to the T-array body.")
    out()
    out("Verdict:")
    out("  The TypeScript community editor does NOT reveal a hidden write path for \"No Part\" birth defects.")
    out("  Its mutation write path only edits the same structured mutation table (our T array), and its UI is limited to IDs >= 300.")
    out("  So this tool is not evidence of any second persisted defect field, and Direction 4a is effectively ruled out as a save-layout lead.")

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
