# Verification Policy (Orchestrator)

How the orchestrator (Opus) handles `[PIVOTAL]` claims in subagent reports. Companion to `verification_mode.md`, which governs the verifier subagent's behavior.

## Retroactive `[PIVOTAL]` flagging

Subagents self-flag `[PIVOTAL]` against the `findings/*.md` they read at task start. They do **not** read `DEFECT_INVESTIGATION.md` and cannot see direction history or the active working model.

The orchestrator must additionally flag `[PIVOTAL]` itself when a non-flagged bullet would:
- (a) Close, open, or invalidate a logged Direction, **or**
- (b) Contradict the active working model in `DEFECT_INVESTIGATION.md`, **or**
- (c) Be the sole basis for the orchestrator changing the next investigation step.

Subagents flag against the stable factual record; the orchestrator retro-flags against the investigation's evolving state. Both pathways feed into the same dispatch rule below.

## When to dispatch a verifier

Any subagent report containing one or more `[PIVOTAL]` bullets — whether self-flagged or retro-flagged — triggers verifier dispatch.

- Multiple `[PIVOTAL]` bullets concerning the same artifact may be batched into one verifier dispatch.
- Bullets concerning different artifacts dispatch separately so each verdict is independent.

## What NOT to do before dispatching

Do not read the raw decompile, raw script output, or raw GON file into your own context. The whole point of this flow is to keep that material in the verifier's context, not Opus's. If you find yourself about to MCP-fetch a function or open an audit file just to "double-check," stop and dispatch a verifier instead.

## Verifier dispatch shape

The dispatch prompt must:
- Quote the `[PIVOTAL]` bullet verbatim.
- Name the artifact (function/offset/address/file:line).
- Point at `defect-investigation/subagents/_shared/verification_mode.md` and require its return shape.
- Explicitly request a verdict: `CONFIRM` / `CONTRADICT` / `INCONCLUSIVE`.

## Choice of verifier subagent type

Match the artifact source:
- Ghidra / decompile claim → `defect-ghidra`
- Save-blob / script claim → `defect-blob-walker`
- GON / corpus claim → `defect-text-resources`

A different *instance* of the same subagent type is the goal — the value is fresh context, not a different toolset.

## Acting on the verdict

- `CONFIRM` → integrate the original finding normally.
- `CONTRADICT` → do not integrate. Either (a) read the artifact yourself (last resort, costs context), or (b) dispatch a third verifier with the disagreement quoted as input.
- `INCONCLUSIVE` → treat as `CONTRADICT` for safety; same options.

## Audit trail

When integrating a `[PIVOTAL]` finding into `DEFECT_INVESTIGATION.md` or any `findings/` doc, append a short note inline:

> Verified by `<subagent>`: CONFIRM (`<one-line verdict summary>`).

The verdict is small enough to inline; no separate audit file is required.
