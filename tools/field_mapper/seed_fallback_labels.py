#!/usr/bin/env python3
"""
Fill missing label columns using parser fallback from raw blobs.

By default:
- only alive cats
- only fills blank label fields
- never overwrites existing non-empty labels
"""

from __future__ import annotations

import argparse
import os
import sqlite3

from common import init_db, norm_path, parse_trait_fallback


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed fallback labels from parser-extracted blob traits")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument(
        "--include-gone",
        action="store_true",
        help="Include gone cats (default alive only)",
    )
    return p.parse_args()


def is_blank(v) -> bool:
    return v is None or str(v).strip() == ""


def join_items(items: list[str]) -> str | None:
    if not items:
        return None
    return ", ".join(items)


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    if not os.path.exists(db_path):
        print(f"[WARN] DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        alive_clause = "" if args.include_gone else "WHERE c.is_alive = 1"
        rows = conn.execute(
            f"""
            SELECT
                c.save_id, c.cat_db_key, c.raw_blob, c.gender_guess,
                l.label_gender, l.label_abilities, l.label_mutations, l.label_disorders
            FROM cats c
            LEFT JOIN labels l ON l.save_id = c.save_id AND l.cat_db_key = c.cat_db_key
            {alive_clause}
            """
        ).fetchall()

        changed = 0
        for row in rows:
            if row["raw_blob"] is None:
                continue

            fallback = parse_trait_fallback(row["raw_blob"])
            label_gender = row["label_gender"]
            label_abilities = row["label_abilities"]
            label_mutations = row["label_mutations"]
            label_disorders = row["label_disorders"]

            if is_blank(label_gender) and not is_blank(row["gender_guess"]):
                label_gender = row["gender_guess"]
            if is_blank(label_abilities):
                label_abilities = join_items(fallback["abilities"])
            if is_blank(label_mutations):
                label_mutations = join_items(fallback["mutations"])
            if is_blank(label_disorders):
                label_disorders = join_items(fallback["disorders"])

            conn.execute(
                """
                INSERT INTO labels (
                    save_id, cat_db_key, label_gender, label_abilities, label_mutations, label_disorders, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(save_id, cat_db_key) DO UPDATE SET
                    label_gender=CASE
                        WHEN labels.label_gender IS NULL OR TRIM(labels.label_gender) = ''
                        THEN excluded.label_gender
                        ELSE labels.label_gender
                    END,
                    label_abilities=CASE
                        WHEN labels.label_abilities IS NULL OR TRIM(labels.label_abilities) = ''
                        THEN excluded.label_abilities
                        ELSE labels.label_abilities
                    END,
                    label_mutations=CASE
                        WHEN labels.label_mutations IS NULL OR TRIM(labels.label_mutations) = ''
                        THEN excluded.label_mutations
                        ELSE labels.label_mutations
                    END,
                    label_disorders=CASE
                        WHEN labels.label_disorders IS NULL OR TRIM(labels.label_disorders) = ''
                        THEN excluded.label_disorders
                        ELSE labels.label_disorders
                    END,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    int(row["save_id"]),
                    int(row["cat_db_key"]),
                    label_gender,
                    label_abilities,
                    label_mutations,
                    label_disorders,
                ),
            )
            changed += 1

        conn.commit()
        print(f"[INFO] Fallback label seed complete. rows_processed={len(rows)} rows_upserted={changed}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

