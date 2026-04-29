# Advisor Strategy

A multi-model workflow pattern for non-trivial tasks. Opus advises and reviews; Sonnet/Haiku implements.

## Roles

- **Opus (adviser):** Reads the relevant code, understands the requirement, identifies risks and edge cases, produces a structured plan, dispatches subagents, then reviews the output. Opus does not edit files in the primary workflow — it reasons, plans, and checks. Direct file edits by Opus are reserved for trivial fixups, CLAUDE.md / memory updates, and the orchestration glue between subagent calls.
- **Sonnet (implementer):** Receives a tight plan from Opus and executes it. Default model for implementation, investigation scripts, refactors, and any task that needs context awareness or judgment.
- **Haiku (mechanical worker):** Reserved for high-volume mechanical tasks — formatting, lint sweeps, generating fixtures, repetitive find-and-replace across many files. Not for anything that requires understanding context.

## The Three-Phase Loop

1. **Plan** — Opus reads what's needed, writes a plan that names file paths, expected behavior, edge cases, and the report format. Vague plans are pushed back on before dispatch, not after.
2. **Execute** — Sonnet (or Haiku) carries out the plan via the Agent tool, returns a summary plus paths to any artifacts produced.
3. **Review** — Opus checks the summary against the plan, spot-checks the artifacts the subagent claims to have produced, and decides whether to accept, iterate, or revise the plan.

The review phase is non-optional. Skipping it to save tokens defeats the strategy.

## When to Skip the Strategy

Use the active model directly (no subagent dispatch) when:

- The task is small and well-defined — typo fix, single-function rename, obvious one-line change.
- The work is exploratory scratchpad — poking around to understand something, with no deliverable.
- The task is genuinely mechanical and high-volume — Haiku territory, but invoke directly rather than wrapping in a planning ceremony.

If the operator started the session on Sonnet, that's a signal the task is bounded — don't spin up Opus orchestration for it.

## Plan Quality Rules

A plan handed to a subagent must include:

- **Specific file paths** — not "the parser", but `src/save_parser.py`.
- **Expected output shape** — what the report should contain, what artifacts to produce, where they go.
- **Constraints** — what not to touch, what conventions to follow, what would count as a failure.
- **Obstacle protocol** — instruct the subagent to stop and surface ambiguity or unexpected blockers in its summary rather than improvise. The plan is a starting point, not a contract; if reality disagrees, control returns to Opus to revise.
- **Closed-leads list (when continuing prior work)** — explicitly enumerate prior findings that must NOT be re-recommended as "next steps." Subagents start cold and pattern-match to obvious-looking next moves; without this list, they will recommend revisiting closed leads. Cheap to include, prevents wasted review cycles.
- **Identity-claim discipline (for code/binary forensics)** — when asking a subagent to identify what a function, address, table, or field IS, instruct it to corroborate the claim with multiple lines of evidence (string refs, callers, signature, expected behavior) rather than inferring identity from one decompile. Treat single-source identity claims as hypotheses that need verification, not conclusions. This prevents the "interesting interpretation gets locked in" failure mode.
- **Verification of pivotal claims (defect investigation)** — when a subagent report contains a `[PIVOTAL]` bullet (a finding that would close/open/invalidate a Direction or contradict a canonical findings doc), do **not** read the raw artifact (decompile, script output, GON dump) into your own context. Dispatch a fresh verifier subagent of the matching type with the claim quoted verbatim and require the verdict shape from `defect-investigation/subagents/_shared/verification_mode.md`. Read only the verdict (`CONFIRM` / `CONTRADICT` / `INCONCLUSIVE`, ≤200 words + ≤5 quoted lines). Full policy: `defect-investigation/subagents/_shared/verification_policy.md`.

## Common Failure Modes

- **Ambiguous plans → Sonnet improvises.** Tighten the plan before dispatch. Name edge cases explicitly.
- **Skipped review → quality drift.** Always run the review phase, even if brief.
- **Shallow review → missed contradictions.** For findings that drive direction changes (not mere rule-outs), second-source the claim. In the defect investigation, that means dispatching a verifier subagent (see Plan Quality Rules above) rather than reading the raw artifact yourself — the goal is to catch summary-flattened ambiguity without bloating orchestrator context.
- **Haiku used where Sonnet fits.** "Looks simple" ≠ "is simple." If the task needs context awareness or judgment, use Sonnet.
- **Stale CLAUDE.md → bad plans.** Update CLAUDE.md and memory as the codebase and investigation state change. Opus plans only as well as the context lets it.
- **Plan treated as sacred.** When Sonnet hits a real obstacle, it should stop and report. Opus revises; Sonnet does not improvise around the gap.
- **Subagent "next step" recommendations adopted uncritically.** Subagents lack full project context and pattern-match to obvious moves, often suggesting closed leads. Treat their recommendations as one input, not a directive. Always validate against the closed-leads list before dispatching.

## Default Model Selection

- Investigation scripts, blob-walking, roster scans, refactors, well-defined fixes → Sonnet.
- Decompile interpretation with multiple plausible readings, ambiguous requirements, subtle correctness, planning, review, documentation updates → Opus.
- Bulk formatting, mechanical regex sweeps across many files → Haiku.

When dispatching a subagent, specify `model:` explicitly. Inheriting the parent model wastes Opus capacity on Sonnet-grade work.
