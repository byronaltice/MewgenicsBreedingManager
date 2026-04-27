# defect-investigation/ Index

## Key Files

- `DEFECT_INVESTIGATION.md` — Master log. Start here. Contains confirmed findings, ruled-out leads, active directions, and next steps. Keep updated after each investigation step.

## Subdirectories

Read AGENTS.md in each listed directory for an index of the directory contents. For each AGENTS.md in each directory, ensure the index remains updated. Index should be descriptive enough to allow the information to be found by agents easily. 

Files and directories listed below are contained within the current directory: `defect-investigation/`.

| File                                              | Purpose                                                                                                                                                        |
|---------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `DEFECT_INVESTIGATION.md`                         | MUST READ before beginning any investigation work. Skip ONLY if your work is not regarding actively investigating the missing defect issue                     |
| `archive/`                                        | Archived scripts, tools, and the field-mapping SQLite database. Move files here when they are no longer useful. (archive-write-only)                           |
| `audit/`                                          | Script and tool output preserved/cached for reference.                                                                                                         |
| `findings/`                                       | Additional, lesser-referenced confirmed findings. To aid in breaking up `DEFECT_INVESTIGATION.md` into digestible chunks. Store less-important findings here in multiple files. Ensure they are indexed in `findings/AGENTS.md` and referenced in `DEFECT_INVESTIGATION.md`. |
| `findings/OBSOLETE.md`                            | Obsolete or incorrect, proven-wrong findings.                                                                                                                  |
| `game-files/resources/`                           | Game's extracted resources.gpak files (read-only). Use these instead of searching the `resources.gpak` file directly.                                          |
| `game-files/saves/`                               | Save file snapshots used during investigation (read and add new snapshots only - preserve old snapshots).                                                      |
| `notes/`                                          | In-game observations that can only be done by the User while running the game, and other user-only notes, such as actual cat defects observed by the user.     |
| `scripts/`                                        | Active investigation scripts to aid in parsing files, reading binaries, interacting with mcp.                                                                  |