# audit/ Index

Preserved script and tool output, cached to avoid re-running expensive probes or binary scans.
All results are organized by direction number under `direction/`.

## direction/ Contents

Each file is named `direction##_results.txt` and holds the raw output for that investigation direction.
Directions without a results file either produced no output or results were captured inline in `DEFECT_INVESTIGATION.md`.

| File                                        | Direction | Summary                                                            |
|---------------------------------------------|-----------|--------------------------------------------------------------------|
| `direction29_results.txt`                   | 29        | FUN_14022cf90 record identification                                |
| `direction30_results.txt`                   | 30        | Post-stat gap decoding before DefaultMove                          |
| `direction31_results.txt`                   | 31        | Ability tail mapping through equipment and class string            |
| `direction32_results.txt`                   | 32        | Executable/resource scan for defect strings and constants          |
| `direction33_results.txt`                   | 33        | Saved body-part T indices mapped to CatPart fields                 |
| `direction34_results.txt`                   | 34        | (see file)                                                         |
| `direction35_results.txt`                   | 35        | (see file)                                                         |
| `direction36_results.txt`                   | 36        | 10 pre-corridor strings roster scan at DefaultMove run             |
| `direction37_results.txt`                   | 37        | (see file)                                                         |
| `direction38_results.txt`                   | 38        | (see file)                                                         |
| `direction39_results.txt`                   | 39        | Three post-class-string fields extracted for all 947 cats          |
| `direction40_results.txt`                   | 40        | GON entries for base-shape IDs 139 (eyes), 23 (eyebrows), 132 (ears) |
| `direction41_results.txt`                   | 41        | stat_mod hidden defect penalty check                               |
| `direction42_results.txt`                   | 42        | (see file)                                                         |
| `direction43_results.txt`                   | 43        | (see file)                                                         |
| `direction46_results.txt`                   | 46        | (see file)                                                         |
| `direction47_b5260_mode_flags_report.txt`   | 47        | FUN_1400b5260 mode/argument behavior and CatPart+0x18 flags        |
| `direction47_review_results.txt`            | 47 review | FUN_140734760 placement-driven present flags                       |
