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

## What NOT to do

- Do not rename functions in Ghidra (you have read-only MCP tools only).
- Do not call `import_binary` or `delete_project_binary`.
- Do not propose function renames in `findings/binary_function_map.md` — surface candidates in your report and let the orchestrator decide.
- Do not paste full decompiles. Cite + quote slices.
