# findings/ Index

Lesser-referenced confirmed findings that support `DEFECT_INVESTIGATION.md`.
Start with `DEFECT_INVESTIGATION.md` for active investigation state — this directory holds stable reference detail.

When adding a new findings file, update this index with a description specific enough that an agent can decide whether to open it without reading it.

## Files

| File                           | Contents                                                                                                  |
|--------------------------------|-----------------------------------------------------------------------------------------------------------|
| `parser_and_gon_reference.md`  | T array structure, mutation stat modifiers, defect detection logic, GPAK GON format, `_VISUAL_MUT_DATA`, known base-shape IDs. Stable unless game save format changes. |
| `blob_corridor_map.md`         | Byte-for-byte map of the per-cat save blob: header through post-equipment tail, body-part container layout, confirmed exhausted regions. |
| `binary_function_map.md`       | All identified Ghidra function names, roles, and key data addresses. Stable lookup table.                 |
| `ruled_out_leads.md`           | Every closed investigation lead with direction citations. Do not re-investigate anything listed here.     |
| `OBSOLETE.md`                  | Findings that were later proven wrong or superseded. Read before treating older findings as valid.        |
