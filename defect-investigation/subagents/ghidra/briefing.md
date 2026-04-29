# Ghidra Subagent Briefing

You analyze `Mewgenics.exe` via the mewgenics-ghidra MCP server. Read-only role.

## Canonical naming source

`defect-investigation/findings/binary_function_map.md` is the canonical record of identified functions, their roles, and key data addresses. Always check it before proposing a new function name. If a function in your task has already been identified there, use that name.

## Reference cats (for anchoring runtime behavior to ground truth)

| Name | db_key | Status | Notes |
|---|---|---|---|
| Whommie | 853 | defect+ | Eye Birth Defect (Blind), Eyebrow Birth Defect (-2 CHA) |
| Bud | 887 | defect+ | Ear Birth Defect (-2 DEX) |
| Kami | 840 | control | Shares Whommie's eye 139 / eyebrow 23 base IDs without defects |
| Petronij | 841 | control | |
| Murisha | 852 | control | |

## MCP tool usage notes

- **`search_symbols_by_name`** and **`list_cross_references`** are cheap; prefer them before broad `search_code`.
- **`decompile_function`** output is large. Extract only the slice needed for the report — do not paste full decompiles into your evidence section. Cite by address and quote ≤10 lines.
- **`gen_callgraph`** is valuable for "who calls X" / "what does X reach" questions.
- **`read_bytes`** for spot-checking specific addresses; avoid for large ranges.

## Identity-claim corroboration patterns

When asked "what is FUN_X", combine at least two of:
- String cross-references near the entry point
- Caller signatures and the contexts they're called from
- Calling convention / argument shape vs. expected role
- Behavioral match against a known runtime observation
- Cross-check against `findings/binary_function_map.md`

If you can only get one, label it **hypothesis** per `investigation_rules.md`.

## Output path convention

You may write **only** to `defect-investigation/audit/direction/`. Every dispatch produces one audit artifact named with this template:

    defect-investigation/audit/direction/directionNN_<topic>_results.txt

- `NN` is the direction number (zero-padded if helpful, e.g. `direction52`).
- `<topic>` is a short snake_case descriptor of the specific task — `xref_scan`, `corridor_trace`, `b5260_mode_flags`, `verification`, `review`, etc. The descriptor exists so multiple agents working the same direction (initial scan, follow-up, verifier) produce distinct files and a future verifier can find the right one without ambiguity.
- The full path goes in the report's **Artifacts written** section.

If the dispatch prompt names a specific filename, use that. Otherwise pick a topic descriptor that summarizes what the file contains.

Do not write anywhere else — not under `findings/`, not under `scripts/`, not next to source files.

## What NOT to do

- Do not rename functions in Ghidra (you have read-only MCP tools only).
- Do not call `import_binary` or `delete_project_binary`.
- Do not propose function renames in `findings/binary_function_map.md` — surface candidates in your report and let the orchestrator decide.
- Do not paste full decompiles. Cite + quote slices.
- Do not write outside `defect-investigation/audit/direction/`.
