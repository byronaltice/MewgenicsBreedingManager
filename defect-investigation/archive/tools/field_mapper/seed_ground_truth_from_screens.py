#!/usr/bin/env python3
"""
Seed labels from screenshot filename ground-truth names.

Rule:
- screenshot filename stem == cat name
- folder contains one .sav file + many .png files
- rows are tagged with ground_truth_source='screenshot'
- label_gender is filled from parser guess only when label is blank
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from pathlib import Path

from common import init_db, norm_path, warn


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed ground-truth labels from screenshot filenames")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument("--screens-root", default="tools/saves", help="Root folder containing save+png subfolders")
    return p.parse_args()


def iter_screen_folders(root: str):
    root_p = Path(root)
    if not root_p.exists():
        return
    for folder in root_p.rglob("*"):
        if not folder.is_dir():
            continue
        savs = list(folder.glob("*.sav"))
        pngs = list(folder.glob("*.png"))
        if savs and pngs:
            yield folder, savs, pngs


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    root = norm_path(args.screens_root)

    if not os.path.exists(db_path):
        warn(f"DB not found: {db_path}")
        return 2
    if not os.path.isdir(root):
        warn(f"Screens root not found: {root}")
        return 2

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)

        save_map = {
            norm_path(row["save_path"]): int(row["save_id"])
            for row in conn.execute("SELECT save_id, save_path FROM saves")
        }

        matched = 0
        missing = 0
        ambiguous = 0
        for folder, savs, pngs in iter_screen_folders(root):
            save_path = norm_path(str(savs[0]))
            save_id = save_map.get(save_path)
            if save_id is None:
                warn(f"No ingested save row for folder save: {save_path}")
                continue

            for png in pngs:
                cat_name = png.stem.strip()
                rows = conn.execute(
                    """
                    SELECT cat_db_key, gender_guess
                    FROM cats
                    WHERE save_id = ?
                      AND LOWER(name) = LOWER(?)
                      AND is_alive = 1
                    ORDER BY cat_db_key
                    """,
                    (save_id, cat_name),
                ).fetchall()

                if not rows:
                    rows = conn.execute(
                        """
                        SELECT cat_db_key, gender_guess
                        FROM cats
                        WHERE save_id = ?
                          AND LOWER(name) = LOWER(?)
                        ORDER BY is_alive DESC, cat_db_key
                        """,
                        (save_id, cat_name),
                    ).fetchall()

                if not rows:
                    missing += 1
                    warn(f"No cat match for screenshot '{png.name}' in save_id={save_id}")
                    continue
                if len(rows) > 1:
                    ambiguous += 1
                    warn(f"Ambiguous cat match for screenshot '{png.name}' in save_id={save_id}")
                    continue

                row = rows[0]
                cat_db_key = int(row["cat_db_key"])
                gender_guess = (row["gender_guess"] or "").strip() or None

                conn.execute(
                    """
                    INSERT INTO labels (
                        save_id, cat_db_key, ground_truth_source, label_gender, notes, updated_at
                    )
                    VALUES (?, ?, 'screenshot', ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(save_id, cat_db_key) DO UPDATE SET
                        ground_truth_source=CASE
                            WHEN labels.ground_truth_source IS NULL OR TRIM(labels.ground_truth_source) = ''
                            THEN 'screenshot'
                            ELSE labels.ground_truth_source
                        END,
                        label_gender=CASE
                            WHEN labels.label_gender IS NULL OR TRIM(labels.label_gender) = ''
                            THEN excluded.label_gender
                            ELSE labels.label_gender
                        END,
                        notes=CASE
                            WHEN labels.notes IS NULL OR TRIM(labels.notes) = ''
                            THEN excluded.notes
                            ELSE labels.notes
                        END,
                        updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        save_id,
                        cat_db_key,
                        gender_guess,
                        f"screenshot:{png.name}",
                    ),
                )
                matched += 1

        conn.commit()
        print(f"[INFO] Ground-truth screenshot seeding complete. matched={matched} missing={missing} ambiguous={ambiguous}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
