# Example Prompts (Text-Resources Subagent)

These are illustrative dispatch prompts. The orchestrator writes the actual prompt; these show shape.

## Example 1 — Tag-based enumeration

> List every GON entry with tag `birth_defect` across `defect-investigation/game-files/resources/gpak-text/data/`. Report file path, line number, and the entry's full body (≤10 lines per entry). Sort by file path.

## Example 2 — ID cross-reference

> Enumerate every mutation ID referenced in `catgen.gon`. For each, identify the body part it applies to. Cross-reference against the defect base-shape IDs (eye=139, eyebrow=23, ear=132) and flag any matches.

## Example 3 — String search with analysis

> Search the entire `gpak-text/data/` corpus for the literal string `"Blind."`. For each hit, report the file, line, and surrounding context. State whether the hit appears to be a defect definition, a tooltip, or something else.

## Example 4 — Completeness check

> The current investigation tracks three defect types: Blind (eyes), -2 CHA (eyebrows), -2 DEX (ears). List every body-part defect entry you find in the corpus and report whether the set is consistent with these three or whether additional defect types exist.
