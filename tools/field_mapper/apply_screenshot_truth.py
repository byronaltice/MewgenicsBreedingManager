#!/usr/bin/env python3
"""
Apply hard screenshot ground-truth labels into the DB.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3

from common import gayness_from_orientation_flag, init_db, norm_path, normalize_orientation_flag


def _to_optional_float(v: str):
    s = (v or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply screenshot-truth CSV into labels table")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument("--csv", default="tools/field_mapper/screenshot_truth.csv", help="Screenshot truth CSV")
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite non-empty label_* values (default only fills blanks)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    csv_path = norm_path(args.csv)
    if not os.path.exists(db_path):
        print(f"[WARN] DB not found: {db_path}")
        return 2
    if not os.path.exists(csv_path):
        print(f"[WARN] CSV not found: {csv_path}")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        save_map = {norm_path(path): int(save_id) for save_id, path in conn.execute("SELECT save_id, save_path FROM saves")}

        updated = 0
        skipped = 0
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                save_path = norm_path((row.get("save_path") or "").strip())
                cat_key_raw = (row.get("cat_db_key") or "").strip()
                if not save_path or not cat_key_raw:
                    skipped += 1
                    continue
                save_id = save_map.get(save_path)
                if save_id is None:
                    skipped += 1
                    continue
                try:
                    cat_db_key = int(cat_key_raw)
                except ValueError:
                    skipped += 1
                    continue

                orientation_flag = normalize_orientation_flag(row.get("label_orientation_flag") or "")
                gayness = _to_optional_float(row.get("label_gayness") or "")
                if gayness is None:
                    gayness = gayness_from_orientation_flag(orientation_flag)

                label_mutations = (row.get("label_mutations") or "").strip() or None
                label_abilities = (row.get("label_abilities") or "").strip() or None
                label_disorders = (row.get("label_disorders") or "").strip() or None
                notes = (row.get("notes") or "").strip() or None

                if args.overwrite:
                    conn.execute(
                        """
                        INSERT INTO labels (
                            save_id, cat_db_key, ground_truth_source, label_orientation_flag, label_gayness,
                            label_mutations, label_abilities, label_disorders, notes, updated_at
                        )
                        VALUES (?, ?, 'screenshot_hardcoded', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(save_id, cat_db_key) DO UPDATE SET
                            ground_truth_source='screenshot_hardcoded',
                            label_orientation_flag=excluded.label_orientation_flag,
                            label_gayness=excluded.label_gayness,
                            label_mutations=excluded.label_mutations,
                            label_abilities=excluded.label_abilities,
                            label_disorders=excluded.label_disorders,
                            notes=excluded.notes,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (
                            save_id,
                            cat_db_key,
                            orientation_flag,
                            gayness,
                            label_mutations,
                            label_abilities,
                            label_disorders,
                            notes,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        INSERT INTO labels (
                            save_id, cat_db_key, ground_truth_source, label_orientation_flag, label_gayness,
                            label_mutations, label_abilities, label_disorders, notes, updated_at
                        )
                        VALUES (?, ?, 'screenshot_hardcoded', ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(save_id, cat_db_key) DO UPDATE SET
                            ground_truth_source=CASE
                                WHEN labels.ground_truth_source IS NULL OR TRIM(labels.ground_truth_source) = ''
                                THEN 'screenshot_hardcoded' ELSE labels.ground_truth_source END,
                            label_orientation_flag=CASE
                                WHEN labels.label_orientation_flag IS NULL OR TRIM(labels.label_orientation_flag) = ''
                                THEN excluded.label_orientation_flag ELSE labels.label_orientation_flag END,
                            label_gayness=CASE
                                WHEN labels.label_gayness IS NULL THEN excluded.label_gayness ELSE labels.label_gayness END,
                            label_mutations=CASE
                                WHEN labels.label_mutations IS NULL OR TRIM(labels.label_mutations) = ''
                                THEN excluded.label_mutations ELSE labels.label_mutations END,
                            label_abilities=CASE
                                WHEN labels.label_abilities IS NULL OR TRIM(labels.label_abilities) = ''
                                THEN excluded.label_abilities ELSE labels.label_abilities END,
                            label_disorders=CASE
                                WHEN labels.label_disorders IS NULL OR TRIM(labels.label_disorders) = ''
                                THEN excluded.label_disorders ELSE labels.label_disorders END,
                            notes=CASE
                                WHEN labels.notes IS NULL OR TRIM(labels.notes) = ''
                                THEN excluded.notes ELSE labels.notes END,
                            updated_at=CURRENT_TIMESTAMP
                        """,
                        (
                            save_id,
                            cat_db_key,
                            orientation_flag,
                            gayness,
                            label_mutations,
                            label_abilities,
                            label_disorders,
                            notes,
                        ),
                    )
                updated += 1

        conn.commit()
    finally:
        conn.close()

    print(f"[INFO] Applied screenshot truth rows: {updated}  skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

