# archive/ Index

Dead-weight files no longer needed for active investigation. Write-only — do not use these for new work.
When archiving, preserve paths relative to repo root (e.g. `tools/foo.py` → `archive/tools/foo.py`).

## Files

- `diag_defects.py`        — Early diagnostic: checks GON files for mutation IDs and scans Whommie's blob for defect values. Findings already documented in `DEFECT_INVESTIGATION.md`.
- `field_mapping.sqlite`   — SQLite database from the field-mapper pipeline. Stored compressed/raw cat blobs and manual ground-truth labels for binary field offset searches. Superseded by documented findings.

## tools/ Subdirectory

### Ghidra Probes (Java)

Each probe was a Ghidra headless script targeting a specific hypothesis. Corresponding `*_output.txt` / `*_utf8.txt` files hold the raw output.

- `GhidraBodyPartFlagProbe.java` / `ghidra_body_part_flag_probe_output.txt`
- `GhidraBodyPartSerializerMap.java` / `ghidra_body_part_serializer_map_output.txt`
- `GhidraCf90Probe.java` / `ghidra_cf90_probe_output.txt` + `ghidra_cf90_probe_utf8.txt`
- `GhidraDecoderProbe.java` / `ghidra_decoder_probe_output.txt`
- `GhidraDefectApplyProbe.java` / `ghidra_defect_apply_probe_output.txt`
- `GhidraDefectDisplayProbe.java` / `ghidra_defect_display_probe_output.txt`
- `GhidraDefectKeyFunctions.java` / `ghidra_defect_key_functions_output.txt`
- `GhidraDefectProbe.java` / `ghidra_defect_probe_output.txt`
- `GhidraDefectRefs.java` / `ghidra_defect_refs_output.txt`
- `GhidraDirection42Probe.java` / `ghidra_direction42_probe_output.txt` + `ghidra_direction42_probe_utf8.txt`
- `GhidraDirection43Probe.java` / `ghidra_direction43_probe_output.txt` + `ghidra_direction43_utf8.txt`
- `GhidraDirection43bProbe.java` / `ghidra_direction43b_probe_output.txt` + `ghidra_direction43b_utf8.txt`
- `GhidraDirection43cProbe.java` / `ghidra_direction43c_probe_output.txt` + `ghidra_direction43c_utf8.txt`
- `GhidraFun14022d360FullDump.java` / `ghidra_fun14022d360_decompile.txt` + `ghidra_fun14022d360_decompile_utf8.txt`
- `GhidraFun1402345e0Dump.java` / `ghidra_fun1402345e0_decompile.txt`
- `GhidraHeadlessProbe.java` / `ghidra_headless_probe.py` / `ghidra_probe_output.txt`
- `GhidraSearchAll.java`
- `Icons.png`              — Icon reference screenshot used during early investigation.
- `field_mapper_README.md`  — Workflow documentation for the field-mapper pipeline (ingest → label → discover). Pipeline is fully archived; kept for reference only.
- `HANDOFF_direction44.md`  — Direction 44 handoff doc. Fully superseded by Directions 44-47 and current `DEFECT_INVESTIGATION.md`.
- `visual_mutation_catalog.py` — Early standalone mutation catalog script, superseded by the app module.
- `mewgenics_analysis-master/` — Early analysis repo snapshot.
- `test-runtimes/`             — Old development environment for decompiling code.
