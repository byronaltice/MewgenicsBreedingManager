#!/usr/bin/env python3
"""
Ingest Mewgenics .sav files into a local SQLite analysis database.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
from typing import Iterable

from common import (
    decompress_cat_blob,
    file_sha256,
    find_save_paths,
    get_alive_key_sets,
    info,
    init_db,
    iter_cats_from_save,
    norm_path,
    parse_cat_known_fields,
    warn,
)

SQLITE_I64_MAX = (1 << 63) - 1
U64_MOD = 1 << 64


def to_sqlite_i64(u: int | None) -> int | None:
    if u is None:
        return None
    if u <= SQLITE_I64_MAX:
        return u
    # Preserve all bits by storing as signed two's-complement i64.
    return u - U64_MOD


def upsert_save(conn: sqlite3.Connection, save_path: str) -> int:
    st = os.stat(save_path)
    sha = file_sha256(save_path)
    conn.execute(
        """
        INSERT INTO saves (save_path, file_mtime, file_size, file_sha256)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(save_path) DO UPDATE SET
            file_mtime=excluded.file_mtime,
            file_size=excluded.file_size,
            file_sha256=excluded.file_sha256,
            ingested_at=CURRENT_TIMESTAMP
        """,
        (save_path, st.st_mtime, st.st_size, sha),
    )
    row = conn.execute("SELECT save_id FROM saves WHERE save_path = ?", (save_path,)).fetchone()
    assert row is not None
    return int(row[0])


def ingest_one_save(conn: sqlite3.Connection, save_path: str, include_gone: bool) -> tuple[int, int, int]:
    save_id = upsert_save(conn, save_path)
    conn.execute("DELETE FROM cats WHERE save_id = ?", (save_id,))
    house_keys, adventure_keys = get_alive_key_sets(save_path)

    ok = 0
    bad = 0
    skipped_gone = 0
    for cat_db_key, comp_blob in iter_cats_from_save(save_path):
        if cat_db_key in adventure_keys:
            status = "Adventure"
            is_alive = 1
        elif cat_db_key in house_keys:
            status = "In House"
            is_alive = 1
        else:
            status = "Gone"
            is_alive = 0

        if not include_gone and not is_alive:
            skipped_gone += 1
            continue

        raw_blob = None
        raw_len = None
        parsed = {
            "parse_ok": 0,
            "parse_error": None,
            "breed_id": None,
            "uid_int": None,
            "unique_id_hex": None,
            "name": None,
            "name_tag": None,
            "name_end_offset": None,
            "parent_uid_a": None,
            "parent_uid_b": None,
            "collar": None,
            "gender_pre_u32_0": None,
            "gender_pre_u32_1": None,
            "gender_pre_u32_2": None,
            "gender_token": None,
            "gender_guess": None,
            "cursor_after_headers": None,
            "str_base": None,
            "dex_base": None,
            "con_base": None,
            "int_base": None,
            "spd_base": None,
            "cha_base": None,
            "lck_base": None,
        }
        try:
            raw_blob = decompress_cat_blob(comp_blob)
            raw_len = len(raw_blob)
            parsed = parse_cat_known_fields(raw_blob)
            ok += 1
        except Exception as e:
            parsed["parse_error"] = f"decompress failed: {e}"
            bad += 1

        conn.execute(
            """
            INSERT INTO cats (
                save_id, cat_db_key, status, is_alive, compressed_blob, raw_blob, raw_len, parse_ok, parse_error,
                breed_id, uid_int, unique_id_hex, name, name_tag, name_end_offset, parent_uid_a, parent_uid_b,
                collar, gender_pre_u32_0, gender_pre_u32_1, gender_pre_u32_2,
                gender_token, gender_guess, cursor_after_headers,
                str_base, dex_base, con_base, int_base, spd_base, cha_base, lck_base
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                save_id,
                cat_db_key,
                status,
                is_alive,
                comp_blob,
                raw_blob,
                raw_len,
                parsed["parse_ok"],
                parsed["parse_error"],
                parsed["breed_id"],
                to_sqlite_i64(parsed["uid_int"]),
                parsed["unique_id_hex"],
                parsed["name"],
                parsed["name_tag"],
                parsed["name_end_offset"],
                parsed["parent_uid_a"],
                parsed["parent_uid_b"],
                parsed["collar"],
                parsed["gender_pre_u32_0"],
                parsed["gender_pre_u32_1"],
                parsed["gender_pre_u32_2"],
                parsed["gender_token"],
                parsed["gender_guess"],
                parsed["cursor_after_headers"],
                parsed["str_base"],
                parsed["dex_base"],
                parsed["con_base"],
                parsed["int_base"],
                parsed["spd_base"],
                parsed["cha_base"],
                parsed["lck_base"],
            ),
        )

    conn.commit()
    return ok, bad, skipped_gone


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Ingest .sav files into a field-mapping SQLite DB")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="Output SQLite DB path")
    p.add_argument("--save", action="append", default=[], help="Path to one .sav file (repeatable)")
    p.add_argument("--save-dir", action="append", default=[], help="Directory to recursively scan for *.sav")
    p.add_argument("--save-glob", action="append", default=[], help="Glob pattern for *.sav files")
    p.add_argument(
        "--include-gone",
        action="store_true",
        help="Include gone cats (default behavior ingests alive cats only)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    save_paths = find_save_paths(args.save, args.save_dir, args.save_glob)
    if not save_paths:
        warn("No save files found. Provide --save, --save-dir, or --save-glob.")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        total_ok = 0
        total_bad = 0
        total_skipped = 0
        for save in save_paths:
            info(f"Ingesting: {save}")
            ok, bad, skipped = ingest_one_save(conn, save, include_gone=args.include_gone)
            total_ok += ok
            total_bad += bad
            total_skipped += skipped
            info(f"  cats parsed: {ok}  decompress failures: {bad}  skipped_gone: {skipped}")

        info(
            f"Done. saves={len(save_paths)} cats_ok={total_ok} "
            f"cats_failed={total_bad} skipped_gone={total_skipped}"
        )
        info(f"DB: {db_path}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
