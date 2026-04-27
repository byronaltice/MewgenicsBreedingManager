# Example Prompts (Blob-Walker Subagent)

These are illustrative dispatch prompts. The orchestrator writes the actual prompt; these show shape.

## Example 1 — Roster scan with control comparison

> Write `scripts/investigate-direction/investigate_direction48.py` that scans all 947 cats for non-zero bytes at blob offset `+0xNNN`. Compare the distribution between defect-positive (Whommie, Bud) and clean controls (Kami, Petronij, Murisha). Output to `audit/direction/direction48_results.txt`. Run it and include the result summary in your report.

## Example 2 — Byte-diff between reference cats

> Write a script that produces a byte-by-byte diff of the post-T region (offset `+0xNNN..+0xMMM`) between Whommie (853) and Kami (840). Highlight any byte where they differ. Output to `audit/direction/direction49_results.txt`.

## Example 3 — Field extraction across roster

> Extend the existing pattern from `investigate_direction39.py`: extract three post-class-string fields for all 947 cats and report which values appear only on Whommie/Bud and not on any clean control.

## Example 4 — Verify a hypothesis with quick check

> Hypothesis: byte at CatData offset `+0xa4` (left-eye CatPart `+0x18` flag) is 0 for Whommie and 1 for Kami after parse. Write a minimal script to verify by reading raw save blobs (not via the existing parser, which doesn't read this field). Output to `audit/direction/direction50_results.txt`.
