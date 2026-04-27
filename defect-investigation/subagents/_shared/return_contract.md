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
