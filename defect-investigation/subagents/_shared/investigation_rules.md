# Investigation Rules

These rules apply to every defect-investigation subagent. Violations waste orchestrator review cycles and can lock in wrong interpretations.

## 1. Closed-leads discipline

Before forming any conclusion, read `defect-investigation/findings/ruled_out_leads.md`.

If a finding restates or revisits a closed lead, you must either:
- **Drop it** — if there's no new evidence, the lead stays closed.
- **Mark it explicitly** — `Re-touches closed lead: <lead name>. Rationale for re-examination: <new evidence>.`

Never present a closed lead as a fresh finding. The orchestrator's review will catch it and the cycle is wasted.

## 2. Identity-claim discipline

Any claim of the form:
- "FUN_X is Y" (function identification)
- "Field at offset +0xNN is Z" (blob field identification)
- "Table at DAT_X holds W" (data table identification)
- "GON entry T means U" (resource identification)

requires **≥2 independent lines of evidence**. Examples of independent evidence:
- String cross-reference + caller signature shape
- Behavioral match (observed runtime effect) + code path match
- Multiple call sites that consistently treat the value the same way
- A known anchor (e.g. `findings/binary_function_map.md`) plus a corroborating signature check

Single-decompile claims must be labeled **hypothesis** with the gap stated:
> Hypothesis: FUN_140xxx may be the visual-mutation applier. Single line of evidence (decompile shape resembles applier pattern). Gap: no caller analysis or string ref yet.

The "interesting interpretation gets locked in" failure mode is the most expensive mistake in this investigation. Treat single-source identity as a hypothesis, not a conclusion.

## 3. Stay in scope

Your tool allowlist is intentionally narrow. If a task seems to require tools you don't have, **stop and report** rather than improvising. The orchestrator will dispatch a different agent or revise the plan.
