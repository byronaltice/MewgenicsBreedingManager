# Field Mapper Workflow

This folder provides a repeatable reverse-engineering pipeline for hidden cat fields.

It is built on **SQLite** because:
- it is already used by the app,
- it needs no new dependencies,
- it is easy to inspect/edit while labeling.

Use DuckDB later only if you hit large-scale analytics limits.

## 1) Ingest save files

```bash
python tools/field_mapper/ingest_saves.py ^
  --db tools/field_mapper/field_mapping.sqlite ^
  --save-dir "%APPDATA%\Glaiel Games\Mewgenics"
```

You can also pass explicit files:

```bash
python tools/field_mapper/ingest_saves.py --save "C:\path\to\file.sav"
```

By default, ingest keeps **alive cats only**. Use `--include-gone` to include gone cats.

## 2) Export labeling template

```bash
python tools/field_mapper/export_label_template.py ^
  --db tools/field_mapper/field_mapping.sqlite ^
  --out tools/field_mapper/labels_template.csv
```

By default, export includes **alive cats only**. Use `--include-gone` to include gone cats.

Fill these columns from in-game observations:
- `label_orientation_flag` (`rainbow` or `pink_blue`)
: mapping rule:
  `rainbow` means gay-only behavior and maps to `label_gayness = 1.0`.
  `pink_blue` means bisexual behavior and maps to `label_gayness = 0.5`.
- `label_gender`
- `label_age`
- `label_libido`
- `label_aggression`
- `label_inbredness`
- `label_gayness`
- `label_abilities` (comma-separated)
- `label_mutations` (comma-separated)
- `label_disorders` (comma-separated)
- `label_lovers` (comma-separated names or IDs)
- `label_haters` (comma-separated names or IDs)

## 3) Import labels

```bash
python tools/field_mapper/import_labels.py ^
  --db tools/field_mapper/field_mapping.sqlite ^
  --csv tools/field_mapper/labels_template.csv
```

## 3c) Seed parser fallback labels (optional)

```bash
python tools/field_mapper/seed_fallback_labels.py ^
  --db tools/field_mapper/field_mapping.sqlite
```

This fills blank `label_gender`, `label_abilities`, `label_mutations`, and `label_disorders`
from parser extraction, without overwriting non-empty labels.

## 3b) Seed screenshot-based hard ground truth

If you have per-cat screenshots named like `Cat Name.png` in folders that also contain the matching `.sav` file:

```bash
python tools/field_mapper/seed_ground_truth_from_screens.py ^
  --db tools/field_mapper/field_mapping.sqlite ^
  --screens-root tools/saves
```

This tags matching rows with `ground_truth_source=screenshot`.

To hardcode screenshot truth (orientation + gayness + traits), generate and fill:

```bash
python tools/field_mapper/build_screenshot_truth_template.py
python tools/field_mapper/apply_screenshot_truth.py
```

`apply_screenshot_truth.py` automatically maps:
- `label_orientation_flag=rainbow` -> `label_gayness=1.0`
- `label_orientation_flag=pink_blue` -> `label_gayness=0.5`

## 4) Discover scalar fields (offset brute-force)

Examples:

```bash
python tools/field_mapper/discover_fields.py --trait gender
python tools/field_mapper/discover_fields.py --trait libido
python tools/field_mapper/discover_fields.py --trait aggression
python tools/field_mapper/discover_fields.py --trait age
python tools/field_mapper/discover_fields.py --trait inbredness
python tools/field_mapper/discover_fields.py --trait gayness
```

Use `--ground-truth-only` to restrict scans to screenshot-tagged rows.

What it scans:
- absolute offsets: `abs+N`
- anchor-relative offsets: `name_end+N`

For each candidate offset/type, it reports support and a quality score.

## 5) Discover set-like traits (ability/mutation/disorder)

```bash
python tools/field_mapper/discover_set_traits.py --trait abilities
python tools/field_mapper/discover_set_traits.py --trait mutations
python tools/field_mapper/discover_set_traits.py --trait disorders
```

Use `--ground-truth-only` to restrict scans to screenshot-tagged rows.

This script:
- scans raw blobs for identifier tokens,
- compares token presence against your labeled sets,
- reports exact-name coverage and top token mappings per labeled term.

## Notes

- Better labels beat more labels. Favor saves where only one or two properties changed.
- For relationships (`lovers`/`haters`), expect graph/list structures keyed by UID and higher ambiguity.
- Re-run ingest/import/discovery as you gather more saves; confidence should improve steadily.
