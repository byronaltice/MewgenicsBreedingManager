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
| `direction34_results.txt`                   | 34        | Birth-defect apply/display path: FUN_1400caa20 (MutatePiece lambda), FUN_1400cb130 (part ID writer), FUN_1400e38c0 (tooltip builder with BirthDefectTooltip) |
| `direction35_results.txt`                   | 35        | Parser coverage of CatData+0x910..0x9b0 effect-list corridor confirmed complete; all four (string, u32) slots read; all "None"/tier-1 for Whommie/Bud |
| `direction36_results.txt`                   | 36        | 10 pre-corridor strings roster scan at DefaultMove run             |
| `direction37_results.txt`                   | 37        | Post-equipment region of FUN_14022d360 mapped: class string, trailing u32/f64 fields, FUN_1402345e0 byte-vector, version-gated fields through v>0x11 |
| `direction38_results.txt`                   | 38        | FUN_1402345e0 confirmed as generic byte-vector serializer (not defect-specific); size=0 for all 5 reference cats |
| `direction39_results.txt`                   | 39        | Three post-class-string fields extracted for all 947 cats          |
| `direction40_results.txt`                   | 40        | GON entries for base-shape IDs 139 (eyes), 23 (eyebrows), 132 (ears) |
| `direction41_results.txt`                   | 41        | stat_mod hidden defect penalty check                               |
| `direction42_results.txt`                   | 42        | Runtime display chain: FUN_1400c9810 reads CatPart+0x18; FUN_1400e38c0 tooltip builder calls FUN_1407b1190; 0xFFFFFFFE → GON block -2 → BirthDefectTooltip |
| `direction43_results.txt`                   | 43        | FUN_1401d2ff0 corrected to GlobalProgressionData::ComputeSaveFilePercentage (not per-cat loader); random_seed lead found; xoshiro256** seeded at TLS+0x178 |
| `direction46_results.txt`                   | 46        | CatPart+0x18 offset puzzle resolved: FUN_1400a5390 and FUN_1400c9810 both read the same flag; earlier +0x24 interpretation was wrong (missing container base +0x60) |
| `direction47_b5260_mode_flags_report.txt`   | 47        | FUN_1400b5260 mode/argument behavior and CatPart+0x18 flags        |
| `direction47_review_results.txt`            | 47 review | FUN_140734760 placement-driven present flags                       |
