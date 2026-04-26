# Handoff: Birth Defect Investigation — Direction 44 onward

## How to start

Read these in order, then begin Direction 44:
1. `CLAUDE.md` section **"Visual Mutation / Birth Defect Parsing"** — full investigation history, ruled-out leads, mapped blob corridor, and "Best Path Forward" (4 prioritized next steps).
2. Memory: `memory/project_defect_investigation.md` (auto-loaded) — current status snapshot.
3. `tools/field_mapper/direction43_results.txt` — most recent findings.

## Operating mode

Use the **Advisor Strategy** documented in `CLAUDE.md` § "Advisor Strategy":
- Opus plans and reviews; does not edit files in the primary workflow.
- Sonnet executes via the Agent tool. Specify `model: "sonnet"` explicitly.
- Subagents must not recommend revisiting closed leads — list them in every prompt.
- Run the review phase on every dispatch. Spot-check the artifacts the subagent claims to have produced.
- Stop and report on contradictions or unexpected blockers — do not improvise.

## Current state

The on-disk per-cat blob is fully mapped byte-for-byte (Directions 33-39). The runtime DISPLAY chain is mapped (Direction 42): `CatPart+0x18 == 0` → effective partID `0xFFFFFFFE` → GON block `-2` (`tag birth_defect`) → `BirthDefectTooltip`. There is no fallback; display strictly requires the substitution.

What's still unknown: how `CatPart+0x18` gets set to 0 for Whommie's eye/eyebrow slots and Bud's ear slot at LOAD time. Direction 42 wrongly identified `FUN_1401d2ff0` as the per-cat save loader; Direction 43 corrected this — `FUN_1401d2ff0` is `GlobalProgressionData::ComputeSaveFilePercentage`, applying progression-milestone mutations. The actual per-cat save loader is unknown.

## Two confirmed facts from the user (2026-04-25)

1. **Defects are stable across save reloads.** Eliminates runtime-randomness hypotheses. Data IS on disk per-cat (explicit field or derivable from a saved seed).
2. **The GON files contain the literal string `"Blind."`** — exact display string for Whommie's Eye Birth Defect. Likely the CSV/locale `desc` for eyes block `-2`. **Use this as a code landmark, not a blob-scan target.** Find the function that produces the `"Blind."` display, then trace BACKWARD to find what saved input drives it. Do NOT re-scan the .sav binary for this string — extensive blob scanning has already been done.

## Direction 44 plan (Sonnet-grade Ghidra task)

**Goal:** Find the real per-cat save loader and trace forward to where defects are applied at load. Identify what saved per-cat input drives defect creation.

**Concrete subtasks for the subagent:**

1. **Find ALL callers of `FUN_14022d360`** (per-cat deserializer). One of them is the per-cat save loader (loops over cats, deserializes each).
2. **Decompile that loader.** Identify what runs immediately AFTER each `FUN_14022d360` call: any defect-applier calls (`FUN_1400ca4a0`, `FUN_1400caa20`, `FUN_1400cb130`, `FUN_1400a5390`, `FUN_1400a5600`)? Any per-body-part loops touching `CatPart+0x18`?
3. **If a defect-application call is found post-deserialize**, trace its arguments: what saved per-cat field does it read? CatData offset, SQLite query with cat-keyed lookup, or GPAK reference?
4. **Full decompile of `FUN_140230750`** (cat save-context loader from Direction 43). It reads `properties.random_seed` but may also read per-cat keys.
5. **Trace from the `"Blind."` GON entry forward to its consumers.** In Ghidra, find the function(s) that read or reference the eyes block `-2` GON entry (where `"Blind."` lives). Walk forward from those references to identify how a cat ends up routed to that entry — that path leads to the saved-input source. This is a complementary back-trace to subtask 1's forward-trace from the loader. Do NOT re-scan the .sav binary for `"Blind."` literally.

**Closed leads — do NOT recommend revisiting:**
- T array (all 72 positions, all ±offsets) — Directions 1-39
- 10 pre-corridor strings at `+0x7d0..+0x8f0` — Direction 36
- `+0x910..+0x9b0` effect-list corridor — Direction 35
- Post-equipment region (`FUN_1402345e0` byte vector, `+0xc08/+0xc09/+0xc0a` u8 flags, `+0x744..+0x780` u32 array) — Directions 37-39
- GPAK GON entries for IDs 139/23/132 — Direction 40
- Saved stat_mod arrays — Direction 41
- `FUN_1401d2ff0` callsite `1401d3c8b` as the load-time defect applier — Direction 43 corrected (it's `ComputeSaveFilePercentage`)

**Reference cats:** Whommie (db_key=853, parent=Kami db_key=840 + Petronij db_key=841), Bud (db_key=887), Murisha (db_key=852, control). Investigation save: `test-saves/investigation/steamcampaign01_20260424_191107.sav`.

**Environment:** Reverse-engineering env setup is in `CLAUDE.md` § "Reverse-Engineering Environment Setup". Set `JAVA_HOME` to the bundled JDK at `test-runtimes/Ghidra/jdk-25.0.2+10`. Use `analyzeHeadless.bat` with `-noanalysis` (the project is already analyzed).

**Output format:** Write the script to `tools/GhidraDirection44Probe.java` (or similar), decompile dumps to `tools/ghidra_direction44_*.txt`, and findings to `tools/field_mapper/direction44_results.txt`.

## Git workflow reminder

Per `CLAUDE.md` § Git: commit each direction locally, merge to main, and push to `origin/main` only at natural stopping points (waiting for user, findings to report). Do not amend prior commits. No `Co-Authored-By` lines.
