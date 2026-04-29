# Subagent Return Contract

Every subagent report must follow this format. The orchestrator integrates reports into `DEFECT_INVESTIGATION.md` and `findings/`; consistent shape makes that mechanical.

## Required sections

### Question
One-line restatement of what was asked. If the task had multiple parts, list them.

### Method
Bulleted list of tools, queries, scripts, or files used. One bullet per distinct action. Keep it terse — this is an audit trail, not a narrative.

### Evidence
Bulleted findings. Every finding cites a source:
- File reference: `path/to/file.py:123`
- Ghidra address or symbol: `FUN_140xxxxxx`, `DAT_xxxxxxxx`, or named symbol
- Save-blob offset: `+0xNNN` (specify whether CatData-relative or container-relative)
- Audit artifact: `audit/direction/directionNN_results.txt:line`
- GON entry: `path/to/file.gon:line` plus the tag

**Pivotal-claim flag.** Prefix any individual finding bullet with `[PIVOTAL]` if it contradicts a stable claim in any `findings/*.md` document you read at task start (the exact set varies by subagent type, but always includes the canonical naming/structure references for your role). Routine confirmations of existing findings stay unmarked. False positives are acceptable; false negatives are the failure mode to avoid — when in doubt, flag. The orchestrator uses `[PIVOTAL]` to decide whether to dispatch a verifier (see `verification_policy.md`).

### Confidence
One of: **High** / **Medium** / **Low**. Follow with one sentence on what additional evidence would raise confidence.

### Open follow-ups
Questions raised but not answered during this task. **Do not phrase as "next steps to investigate" or "recommended directions"** — direction selection is the orchestrator's job, not yours. Phrase as questions: "Is X also true for Y?", "Does Z hold under condition W?"

### Artifacts written
Full paths to any new files (scripts, audit results, briefings). If none, write "None."

## Anti-patterns

- Do not include a "Recommended next directions" or "Suggested follow-up investigation" section. The orchestrator owns direction selection.
- Do not summarize closed leads as new findings (see investigation_rules.md).
- Do not include speculation as evidence. Speculation belongs under Open follow-ups, phrased as a question.

---

## Dispatch rules (orchestrator-facing)

When writing a dispatch prompt, the orchestrator must:

- **Only request artifact writes to `defect-investigation/audit/direction/directionNN_<topic>_results.txt`.** All three subagent types (`defect-ghidra`, `defect-blob-walker`, `defect-text-resources`) are scoped to that directory only. Asking a subagent to write to `findings/`, `scripts/`, or anywhere else will fail or be silently ignored — those paths are orchestrator territory.
- **Pick a descriptive `<topic>` for each dispatch** so multiple artifacts in the same direction don't collide. Examples: `xref_scan`, `corridor_trace`, `verification`, `review`. State the full filename in the dispatch prompt so verifier subagents in later sessions can find the right file unambiguously.
- **Always request an audit artifact for non-trivial work.** The artifact is the durable record — without it, the subagent's findings live only in the transcript, which is opaque to the orchestrator's context. If the work is too small to merit a file (e.g. a single decompile spot-check), say so explicitly in the dispatch prompt and require the inline report only.
