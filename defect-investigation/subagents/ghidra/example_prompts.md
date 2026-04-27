# Example Prompts (Ghidra Subagent)

These are illustrative dispatch prompts. The orchestrator writes the actual prompt; these show shape.

## Example 1 — Function role identification

> Decompile `FUN_140734760` and report whether it reads or writes any byte at `CatPart+0x18`. Cross-reference its callers to determine when it runs during the cat load chain. Corroborate any identity claim with ≥2 lines of evidence.

## Example 2 — Caller analysis

> List all callers of `FUN_140734760`. For each caller, report whether it appears in the per-cat load path documented in `findings/binary_function_map.md` (Direction 45 chain). Flag any caller that does not.

## Example 3 — String reference search

> Search for string `"CatHeadPlacements"` in `Mewgenics.exe`. Report every function that references it, with a one-line role-guess for each (label as hypothesis if single-source).

## Example 4 — Cross-reference verification

> `findings/binary_function_map.md` records `FUN_14005dfd0` as the body-part container constructor that writes byte=1 at `CatPart+0x18` for all 19 CatParts. Verify this by listing its callers and confirming the write pattern matches the recorded CatData offsets. Report any discrepancies.
