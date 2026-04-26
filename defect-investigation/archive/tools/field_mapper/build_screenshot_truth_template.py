#!/usr/bin/env python3
"""
Build CSV template from screenshot files for hard ground-truth labels.
"""

from __future__ import annotations

import argparse
import csv
import os
import sqlite3
from pathlib import Path

from common import init_db, norm_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build screenshot-truth CSV template")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument("--screens-root", default="tools/saves", help="Root folder containing screenshot subfolders")
    p.add_argument("--out", default="tools/field_mapper/screenshot_truth.csv", help="Output CSV path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    root = norm_path(args.screens_root)
    out_path = norm_path(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        save_map = {norm_path(r["save_path"]): int(r["save_id"]) for r in conn.execute("SELECT save_id, save_path FROM saves")}

        rows = []
        for folder in Path(root).rglob("*"):
            if not folder.is_dir():
                continue
            savs = list(folder.glob("*.sav"))
            pngs = list(folder.glob("*.png"))
            if not savs or not pngs:
                continue
            save_path = norm_path(str(savs[0]))
            save_id = save_map.get(save_path)
            if save_id is None:
                continue
            for png in pngs:
                cat_name = png.stem.strip()
                cat_row = conn.execute(
                    """
                    SELECT cat_db_key, is_alive
                    FROM cats
                    WHERE save_id = ? AND LOWER(name) = LOWER(?)
                    ORDER BY is_alive DESC, cat_db_key
                    LIMIT 1
                    """,
                    (save_id, cat_name),
                ).fetchone()
                if not cat_row:
                    continue
                rows.append(
                    {
                        "save_path": save_path,
                        "cat_db_key": int(cat_row["cat_db_key"]),
                        "name": cat_name,
                        "is_alive": int(cat_row["is_alive"]) if cat_row["is_alive"] is not None else "",
                        "label_orientation_flag": "",
                        "label_gayness": "",
                        "label_mutations": "",
                        "label_abilities": "",
                        "label_disorders": "",
                        "notes": f"screenshot:{png.name}",
                    }
                )
    finally:
        conn.close()

    rows.sort(key=lambda r: (r["save_path"], r["name"].lower(), int(r["cat_db_key"])))

    fields = [
        "save_path",
        "cat_db_key",
        "name",
        "is_alive",
        "label_orientation_flag",
        "label_gayness",
        "label_mutations",
        "label_abilities",
        "label_disorders",
        "notes",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"[INFO] Wrote {len(rows)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

