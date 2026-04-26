#!/usr/bin/env python3
"""
Export a CSV template for manual in-game labeling.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3

from common import init_db, norm_path, warn


LABEL_COLUMNS = [
    "label_orientation_flag",
    "label_gender",
    "label_age",
    "label_libido",
    "label_aggression",
    "label_inbredness",
    "label_gayness",
    "label_abilities",
    "label_mutations",
    "label_disorders",
    "label_lovers",
    "label_haters",
    "notes",
]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Export labeling template CSV from field_mapping DB")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument("--out", default="tools/field_mapper/labels_template.csv", help="CSV output path")
    p.add_argument("--save-like", default=None, help="Optional SQL LIKE filter on save path")
    p.add_argument(
        "--include-gone",
        action="store_true",
        help="Include gone cats (default exports alive cats only)",
    )
    p.add_argument(
        "--only-missing",
        action="store_true",
        help="Only export rows where one or more label fields are empty",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    if not os.path.exists(db_path):
        warn(f"DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        where = []
        params: list[object] = []
        if args.save_like:
            where.append("s.save_path LIKE ?")
            params.append(args.save_like)

        if args.only_missing:
            empties = []
            for col in LABEL_COLUMNS:
                empties.append(f"l.{col} IS NULL OR TRIM(CAST(l.{col} AS TEXT)) = ''")
            where.append("(" + " OR ".join(empties) + ")")
        if not args.include_gone:
            where.append("c.is_alive = 1")

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql = f"""
            SELECT
                s.save_path,
                c.cat_db_key,
                c.uid_int,
                c.unique_id_hex,
                c.name,
                c.name_tag,
                c.status,
                c.is_alive,
                c.gender_guess,
                c.gender_token,
                c.gender_pre_u32_0, c.gender_pre_u32_1, c.gender_pre_u32_2,
                c.str_base, c.dex_base, c.con_base, c.int_base, c.spd_base, c.cha_base, c.lck_base,
                l.ground_truth_source,
                l.label_orientation_flag,
                l.label_gender, l.label_age, l.label_libido, l.label_aggression, l.label_inbredness, l.label_gayness,
                l.label_abilities, l.label_mutations, l.label_disorders,
                l.label_lovers, l.label_haters, l.notes
            FROM cats c
            JOIN saves s ON s.save_id = c.save_id
            LEFT JOIN labels l ON l.save_id = c.save_id AND l.cat_db_key = c.cat_db_key
            {where_sql}
            ORDER BY s.save_path, c.name, c.cat_db_key
        """
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()

    out_path = norm_path(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = [
        "save_path",
        "cat_db_key",
        "uid_int",
        "unique_id_hex",
        "name",
        "name_tag",
        "status",
        "is_alive",
        "gender_guess",
        "gender_token",
        "gender_pre_u32_0",
        "gender_pre_u32_1",
        "gender_pre_u32_2",
        "str_base",
        "dex_base",
        "con_base",
        "int_base",
        "spd_base",
        "cha_base",
        "lck_base",
        "ground_truth_source",
        "label_orientation_flag",
        "label_gender",
        "label_age",
        "label_libido",
        "label_aggression",
        "label_inbredness",
        "label_gayness",
        "label_abilities",
        "label_mutations",
        "label_disorders",
        "label_lovers",
        "label_haters",
        "notes",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})

    print(f"[INFO] Exported {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
