#!/usr/bin/env python3
"""
Import manual labels from CSV into the field-mapping SQLite DB.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from typing import Optional

from common import gayness_from_orientation_flag, init_db, norm_path, normalize_orientation_flag, warn


def _to_optional_float(v: str) -> Optional[float]:
    s = (v or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Import labels CSV into field_mapping DB")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument("--csv", default="tools/field_mapper/labels_template.csv", help="CSV input path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    csv_path = norm_path(args.csv)

    if not os.path.exists(db_path):
        warn(f"DB not found: {db_path}")
        return 2
    if not os.path.exists(csv_path):
        warn(f"CSV not found: {csv_path}")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)

        save_rows = conn.execute("SELECT save_id, save_path FROM saves").fetchall()
        save_id_by_path = {norm_path(path): int(save_id) for save_id, path in save_rows}

        inserted = 0
        skipped = 0
        with open(csv_path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                save_path = norm_path((row.get("save_path") or "").strip())
                cat_key_raw = (row.get("cat_db_key") or "").strip()
                if not save_path or not cat_key_raw:
                    skipped += 1
                    continue

                save_id = save_id_by_path.get(save_path)
                if save_id is None:
                    skipped += 1
                    continue

                try:
                    cat_db_key = int(cat_key_raw)
                except ValueError:
                    skipped += 1
                    continue

                exists = conn.execute(
                    "SELECT 1 FROM cats WHERE save_id = ? AND cat_db_key = ?",
                    (save_id, cat_db_key),
                ).fetchone()
                if not exists:
                    skipped += 1
                    continue

                orientation_flag = normalize_orientation_flag(row.get("label_orientation_flag") or "")
                gayness = _to_optional_float(row.get("label_gayness") or "")
                if gayness is None:
                    gayness = gayness_from_orientation_flag(orientation_flag)

                conn.execute(
                    """
                    INSERT INTO labels (
                        save_id, cat_db_key, ground_truth_source, label_orientation_flag, label_gender, label_age, label_libido,
                        label_aggression, label_inbredness, label_gayness,
                        label_abilities, label_mutations, label_disorders,
                        label_lovers, label_haters, notes, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(save_id, cat_db_key) DO UPDATE SET
                        ground_truth_source=excluded.ground_truth_source,
                        label_orientation_flag=excluded.label_orientation_flag,
                        label_gender=excluded.label_gender,
                        label_age=excluded.label_age,
                        label_libido=excluded.label_libido,
                        label_aggression=excluded.label_aggression,
                        label_inbredness=excluded.label_inbredness,
                        label_gayness=excluded.label_gayness,
                        label_abilities=excluded.label_abilities,
                        label_mutations=excluded.label_mutations,
                        label_disorders=excluded.label_disorders,
                        label_lovers=excluded.label_lovers,
                        label_haters=excluded.label_haters,
                        notes=excluded.notes,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        save_id,
                        cat_db_key,
                        (row.get("ground_truth_source") or "").strip() or None,
                        orientation_flag,
                        (row.get("label_gender") or "").strip() or None,
                        _to_optional_float(row.get("label_age") or ""),
                        _to_optional_float(row.get("label_libido") or ""),
                        _to_optional_float(row.get("label_aggression") or ""),
                        _to_optional_float(row.get("label_inbredness") or ""),
                        gayness,
                        (row.get("label_abilities") or "").strip() or None,
                        (row.get("label_mutations") or "").strip() or None,
                        (row.get("label_disorders") or "").strip() or None,
                        (row.get("label_lovers") or "").strip() or None,
                        (row.get("label_haters") or "").strip() or None,
                        (row.get("notes") or "").strip() or None,
                    ),
                )
                inserted += 1

        conn.commit()
    finally:
        conn.close()

    print(f"[INFO] Imported/updated labels: {inserted}  skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
