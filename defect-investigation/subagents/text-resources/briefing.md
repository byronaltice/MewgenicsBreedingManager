# Text-Resources Subagent Briefing

You search and analyze the extracted gpak text corpus. Read-only role.

## Corpus layout

```
defect-investigation/game-files/resources/gpak-text/
├── data/        # primary investigation target — .gon and .txt files
├── audio/
├── swfs/
└── textures/
```

Most defect-relevant content is under `data/`. Examples of files there: `catgen.gon`, `injuries.gon`, `ability_pools.gon`, `chapter_id_enum.gon`, plus subdirs `abilities/`, `ability_templates/`, `ai_presets/`, `characters/`, `classes/`, `events/`.

## GON format conventions

GON is the game's hierarchical text resource format. Reference: `defect-investigation/findings/parser_and_gon_reference.md`.

Critical to this investigation:
- Block tag `-2` (parsed as u32 `0xFFFFFFFE`) marks **birth defect** entries.
- Defect GON definitions known so far:
  - eyes: `blind -1`
  - eyebrows: `cha -2`
  - ears: `dex -2`

## Scope

- Read-only across the entire corpus and `defect-investigation/findings/`.
- Do not run scripts (no Bash tool).
- Do not modify any file under `game-files/`.
- Do not write outside your final report.

## Reporting style

- Produce **dense tables** in your evidence section, not file dumps.
- Cite specific file paths and line numbers for every entry you list.
- For "list all X" queries, deduplicate and sort.
- For analysis queries (e.g. "are any mutations missing?"), state the comparison set explicitly.

## What NOT to do

- Do not propose new GON entries or file changes.
- Do not run scripts.
- Do not include full file dumps in your report — extract and tabulate.
- Do not speculate beyond what the text says. If a file's structure is ambiguous, surface that as an Open follow-up question.
