# scripts/ Index

Active Python investigation scripts for parsing save files, reading binaries, and driving analysis.
These are dev/research tools — not part of the app.

## Files

- `common.py` — Shared helpers (binary reading, save parsing, blob utilities) imported by all direction scripts.

## investigate-direction/

Direction-specific investigation scripts. Each targets a specific hypothesis; see `audit/direction/direction##_results.txt` for the corresponding output.

- `investigate_direction29.py` — Confirms `FUN_14022cf90` = stat arrays (`stat_base`, `stat_mod`, `stat_sec`).
- `investigate_direction30.py` — Maps `CatData+0x788` token string and empty `FUN_14022d100` header.
- `investigate_direction31.py` — Maps the DefaultMove run, three tail `(string, u32)` slots, equipment block, and class string.
- `investigate_direction32.py` — Searches `Mewgenics.exe` and `resources.gpak` for defect strings/constants; maps hits to virtual addresses.
- `investigate_direction33.py` — Writes T-index-to-CatPart map and per-slot dumps for focus cats.
- `investigate_direction36.py` — Roster-scans all 947 cats for unique tokens in the 10 pre-corridor strings.
- `investigate_direction39.py` — Extracts three post-class-string fields for all 947 cats.
- `investigate_direction40.py` — Inspects GON entries for base-shape IDs 139 (eyes), 23 (eyebrows), 132 (ears).
- `investigate_direction41.py` — Checks whether `stat_mod` encodes hidden defect penalties.
