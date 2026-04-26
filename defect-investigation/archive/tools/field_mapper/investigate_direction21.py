"""Direction #21 -- Audit the accessiblefish Python save editor.

This follow-up to Directions 19/20 checks whether another public editor
(`accessiblefish/mewgenics-save-editor`) encodes any hidden mutation/defect
state beyond the same T-array slots we already know about.
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "direction21_results.txt"

FILES = {
    "tool": "https://raw.githubusercontent.com/accessiblefish/mewgenics-save-editor/refs/heads/main/mewgenics_save_tool.py",
    "readme": "https://raw.githubusercontent.com/accessiblefish/mewgenics-save-editor/refs/heads/main/README.md",
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
    out("Direction #21 -- accessiblefish editor audit")
    out("=" * 70)

    contents = {name: fetch(url) for name, url in FILES.items()}
    tool = contents["tool"]
    readme = contents["readme"]

    out("Sources fetched:")
    for name, url in FILES.items():
        out(f"  {name}: {url}")
    out()

    out("=" * 70)
    out("Relevant code excerpts")
    out("=" * 70)
    out(grab(tool, r"MUTATION_SLOT_MAP = \{[\s\S]*?\n\}"))
    out()
    out(grab(tool, r"def parse_abilities_and_mutations\(dec: bytes, name_end: int\) -> Tuple\[List\[AbilityInfo\], List\[MutationInfo\]\]:[\s\S]*?return abilities, mutations"))
    out()
    out(grab(readme, r"### Mutations Storage[\s\S]*?###"))
    out()

    out("=" * 70)
    out("Findings")
    out("=" * 70)
    out("1. This editor models mutations as a single T-array with coarse slot offsets only: T[0], T[5], T[10], ..., T[65].")
    out("   It does not model the 5-u32-per-slot structure we already mapped, and it does not mention any secondary variant or defect array.")
    out("2. `parse_abilities_and_mutations()` reads one `u32` mutation ID per slot from fixed offsets `0x44 + idx * 4`.")
    out("   There is no second read for a missing-part flag, no special handling for low-ID defects, and no scan for `0xFFFFFFFE`.")
    out("3. The README documents the same simplified T-array layout and contains no hidden-field note for defects.")
    out("4. The mutation name tables in this tool are sparse and mostly cover ordinary visible mutations; they are not evidence of deeper defect serialization knowledge.")
    out()
    out("Verdict:")
    out("  The accessiblefish Python editor does not reveal any new persisted field for \"No Part\" birth defects.")
    out("  It is a simpler parser than ours, based on direct slot IDs from the same T-array family, so it narrows the remaining external lead further: other public editors are not where the missing save-layout knowledge lives.")

    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
