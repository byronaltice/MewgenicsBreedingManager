"""Direction #10 -- Dump GPAK mutation data for eyes / eyebrows / ears.

Parse resources.gpak and list every block in eyes.gon, eyebrows.gon, ears.gon
along with its (display_name, stat_desc, is_birth_defect) classification.

If block 139 in eyes.gon, block 23 in eyebrows.gon, or block 132 in ears.gon
have tag birth_defect (or anything unusual), that would directly explain the
missing-defect bug.

Also dumps the raw GON source for each of those specific blocks so we can see
what the file actually says.
"""
from __future__ import annotations

import sys
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import GameData, _parse_mutation_gon, _load_gpak_text_strings  # noqa: E402

GPAK = ROOT / "test-saves" / "resources.gpak"
OUT = Path(__file__).parent / "direction10_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode())
    _lines.append(msg)


def main() -> None:
    out("=" * 70)
    out("Direction #10 -- GPAK mutation data for eyes / eyebrows / ears")
    out("=" * 70)
    out(f"GPAK: {GPAK}\n")

    with open(GPAK, "rb") as f:
        count = struct.unpack("<I", f.read(4))[0]
        entries = []
        for _ in range(count):
            name_len = struct.unpack("<H", f.read(2))[0]
            name = f.read(name_len).decode("utf-8", errors="replace")
            size = struct.unpack("<I", f.read(4))[0]
            entries.append((name, size))
        dir_end = f.tell()

        file_offsets: dict[str, tuple[int, int]] = {}
        offset = dir_end
        for name, size in entries:
            file_offsets[name] = (offset, size)
            offset += size

        game_strings = _load_gpak_text_strings(f, file_offsets)

        for category in ("eyes", "eyebrows", "ears", "legs", "arms"):
            fname = f"data/mutations/{category}.gon"
            if fname not in file_offsets:
                out(f"  MISSING: {fname}")
                continue
            foff, fsz = file_offsets[fname]
            f.seek(foff)
            content = f.read(fsz).decode("utf-8", errors="replace")

            out("=" * 70)
            out(f"GON FILE: {fname} ({fsz} bytes)")
            out("=" * 70)

            parsed = _parse_mutation_gon(content, game_strings, category)
            out(f"Parsed {len(parsed)} entries")
            for slot_id in sorted(parsed.keys()):
                disp, stat_desc, is_def = parsed[slot_id]
                flag = " [BIRTH_DEFECT]" if is_def else ""
                out(f"  id={slot_id:>11} {disp!r:35s} stat_desc={stat_desc!r}{flag}")
            out("")

            # Targeted raw dump of specific IDs
            probe_ids = {
                "eyes": [139, 23, 132, 301, 2, -2],
                "eyebrows": [139, 23, 428, 2, -2],
                "ears": [132, 30, 101, 413, 2, -2],
                "legs": [53, 707, 308],
                "arms": [203, 441],
            }.get(category, [])

            out(f"-- Raw GON blocks for target IDs in {category}: --")
            for target_id in probe_ids:
                # Match both positive and -2 form
                if target_id == -2:
                    match = re.search(r"(?m)^-2\s*\{", content)
                else:
                    match = re.search(rf"(?m)^\s*{target_id}\s*\{{", content)
                if not match:
                    out(f"  id={target_id}: (not found)")
                    continue
                start = match.end()
                depth = 1
                end = start
                while end < len(content) and depth > 0:
                    if content[end] == "{":
                        depth += 1
                    elif content[end] == "}":
                        depth -= 1
                    end += 1
                # Include 200 chars before for context (display name comment)
                context_start = max(0, match.start() - 200)
                block_text = content[context_start:end]
                out(f"  id={target_id}:")
                for line in block_text.splitlines()[-20:]:
                    out(f"    | {line}")
                out("")


    OUT.write_text("\n".join(_lines), encoding="utf-8", errors="replace")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
