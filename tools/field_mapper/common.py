#!/usr/bin/env python3
"""
Shared helpers for save-field reverse engineering.
"""

from __future__ import annotations

import glob
import hashlib
import os
import re
import sqlite3
import struct
from pathlib import Path
from typing import Optional

import lz4.block

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
JUNK_STRINGS = frozenset({"none", "null", "", "defaultmove", "default_move"})

ORIENTATION_TO_GAYNESS = {
    "rainbow": 1.0,
    "gay": 1.0,
    "pink_blue": 0.5,
    "pinkblue": 0.5,
    "bisexual": 0.5,
    "bi": 0.5,
}


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def norm_path(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_save_paths(
    save_files: list[str],
    save_dirs: list[str],
    save_globs: list[str],
) -> list[str]:
    found: set[str] = set()

    for p in save_files:
        p2 = norm_path(p)
        if os.path.isfile(p2):
            found.add(p2)

    for d in save_dirs:
        d2 = norm_path(d)
        if not os.path.isdir(d2):
            continue
        for path in Path(d2).rglob("*.sav"):
            found.add(norm_path(str(path)))

    for pattern in save_globs:
        for p in glob.glob(pattern):
            p2 = norm_path(p)
            if os.path.isfile(p2):
                found.add(p2)

    return sorted(found)


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS saves (
            save_id INTEGER PRIMARY KEY AUTOINCREMENT,
            save_path TEXT NOT NULL UNIQUE,
            file_mtime REAL NOT NULL,
            file_size INTEGER NOT NULL,
            file_sha256 TEXT NOT NULL,
            ingested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cats (
            save_id INTEGER NOT NULL,
            cat_db_key INTEGER NOT NULL,
            status TEXT,
            is_alive INTEGER NOT NULL DEFAULT 1,
            compressed_blob BLOB NOT NULL,
            raw_blob BLOB,
            raw_len INTEGER,
            parse_ok INTEGER NOT NULL DEFAULT 0,
            parse_error TEXT,
            breed_id INTEGER,
            uid_int INTEGER,
            unique_id_hex TEXT,
            name TEXT,
            name_tag TEXT,
            name_end_offset INTEGER,
            parent_uid_a INTEGER,
            parent_uid_b INTEGER,
            collar TEXT,
            gender_pre_u32_0 INTEGER,
            gender_pre_u32_1 INTEGER,
            gender_pre_u32_2 INTEGER,
            gender_token TEXT,
            gender_guess TEXT,
            cursor_after_headers INTEGER,
            str_base INTEGER,
            dex_base INTEGER,
            con_base INTEGER,
            int_base INTEGER,
            spd_base INTEGER,
            cha_base INTEGER,
            lck_base INTEGER,
            PRIMARY KEY (save_id, cat_db_key),
            FOREIGN KEY (save_id) REFERENCES saves(save_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            save_id INTEGER NOT NULL,
            cat_db_key INTEGER NOT NULL,
            ground_truth_source TEXT,
            label_orientation_flag TEXT,
            label_gender TEXT,
            label_age REAL,
            label_libido REAL,
            label_aggression REAL,
            label_inbredness REAL,
            label_gayness REAL,
            label_abilities TEXT,
            label_mutations TEXT,
            label_disorders TEXT,
            label_lovers TEXT,
            label_haters TEXT,
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (save_id, cat_db_key),
            FOREIGN KEY (save_id, cat_db_key) REFERENCES cats(save_id, cat_db_key)
                ON DELETE CASCADE
        )
        """
    )
    _ensure_column(conn, "cats", "status", "TEXT")
    _ensure_column(conn, "cats", "is_alive", "INTEGER")
    _ensure_column(conn, "cats", "name_tag", "TEXT")
    _ensure_column(conn, "cats", "gender_pre_u32_0", "INTEGER")
    _ensure_column(conn, "cats", "gender_pre_u32_1", "INTEGER")
    _ensure_column(conn, "cats", "gender_pre_u32_2", "INTEGER")
    _ensure_column(conn, "labels", "ground_truth_source", "TEXT")
    _ensure_column(conn, "labels", "label_orientation_flag", "TEXT")
    _ensure_column(conn, "labels", "label_abilities", "TEXT")
    _ensure_column(conn, "labels", "label_mutations", "TEXT")
    _ensure_column(conn, "labels", "label_disorders", "TEXT")
    _ensure_column(conn, "labels", "label_gayness", "REAL")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cats_uid ON cats(uid_int)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cats_name ON cats(name)")
    conn.commit()


def _ensure_column(conn: sqlite3.Connection, table_name: str, column_name: str, column_type: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing = {str(r[1]).lower() for r in rows}
    if column_name.lower() not in existing:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


class BinaryReader:
    def __init__(self, data: bytes, pos: int = 0):
        self.data = data
        self.pos = pos

    def _require(self, n: int) -> None:
        if self.pos + n > len(self.data):
            raise ValueError("Out of bounds read")

    def u32(self) -> int:
        self._require(4)
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def i32(self) -> int:
        self._require(4)
        v = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        return v

    def u64(self) -> int:
        self._require(8)
        lo, hi = struct.unpack_from("<II", self.data, self.pos)
        self.pos += 8
        return lo + hi * 4_294_967_296

    def f64(self) -> float:
        self._require(8)
        v = struct.unpack_from("<d", self.data, self.pos)[0]
        self.pos += 8
        return v

    def str(self) -> Optional[str]:
        start = self.pos
        try:
            length = self.u64()
            if length < 0 or length > 20_000:
                self.pos = start
                return None
            self._require(int(length))
            s = self.data[self.pos : self.pos + int(length)].decode("utf-8", errors="ignore")
            self.pos += int(length)
            return s
        except Exception:
            self.pos = start
            return None

    def utf16str(self) -> str:
        char_count = self.u64()
        byte_len = int(char_count * 2)
        self._require(byte_len)
        s = self.data[self.pos : self.pos + byte_len].decode("utf-16le", errors="ignore")
        self.pos += byte_len
        return s

    def skip(self, n: int) -> None:
        self._require(n)
        self.pos += n

    def seek(self, n: int) -> None:
        if n < 0 or n > len(self.data):
            raise ValueError("Seek out of bounds")
        self.pos = n

    def remaining(self) -> int:
        return len(self.data) - self.pos


def normalize_gender_token(raw_gender: Optional[str]) -> Optional[str]:
    g = (raw_gender or "").strip().lower()
    if g.startswith("male"):
        return "male"
    if g.startswith("female"):
        return "female"
    if g.startswith("spidercat"):
        return "?"
    return None


def normalize_orientation_flag(raw_flag: Optional[str]) -> Optional[str]:
    s = (raw_flag or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not s:
        return None
    if s in ("rainbow", "gay"):
        return "rainbow"
    if s in ("pink_blue", "pinkblue", "bi", "bisexual"):
        return "pink_blue"
    return None


def gayness_from_orientation_flag(raw_flag: Optional[str]) -> Optional[float]:
    f = normalize_orientation_flag(raw_flag)
    if f is None:
        return None
    return ORIENTATION_TO_GAYNESS.get(f)


def decompress_cat_blob(blob: bytes) -> bytes:
    if len(blob) < 4:
        raise ValueError("Blob too short for LZ4 size header")
    uncomp_size = struct.unpack("<I", blob[:4])[0]
    return lz4.block.decompress(blob[4:], uncompressed_size=uncomp_size)


def parse_cat_known_fields(raw: bytes) -> dict:
    """
    Parse stable anchors only. Unknown/experimental fields are intentionally not decoded here.
    """
    out = {
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
        r = BinaryReader(raw)
        out["breed_id"] = r.u32()
        uid_int = r.u64()
        out["uid_int"] = uid_int
        out["unique_id_hex"] = hex(uid_int)
        out["name"] = r.utf16str()
        name_end = r.pos
        out["name_end_offset"] = name_end

        out["name_tag"] = r.str() or ""
        out["parent_uid_a"] = r.u64()
        out["parent_uid_b"] = r.u64()
        out["collar"] = r.str() or ""
        _ = r.u32()
        r.skip(64)

        table = [r.u32() for _ in range(72)]
        _ = table

        out["gender_pre_u32_0"] = r.u32()
        out["gender_pre_u32_1"] = r.u32()
        out["gender_pre_u32_2"] = r.u32()
        raw_gender = r.str()
        out["gender_token"] = raw_gender
        out["gender_guess"] = normalize_gender_token(raw_gender)
        _ = r.f64()

        bases = [r.u32() for _ in range(7)]
        (
            out["str_base"],
            out["dex_base"],
            out["con_base"],
            out["int_base"],
            out["spd_base"],
            out["cha_base"],
            out["lck_base"],
        ) = bases

        out["cursor_after_headers"] = r.pos
        out["parse_ok"] = 1
        return out
    except Exception as e:
        out["parse_error"] = str(e)
        return out


def _valid_str(s: Optional[str]) -> bool:
    return bool(s) and s.strip().lower() not in JUNK_STRINGS


VISUAL_MUT_NAMES = [
    "Body",
    "Head",
    "Tail",
    "Rear Leg (L)",
    "Rear Leg (R)",
    "Front Leg (L)",
    "Front Leg (R)",
    "Eye (L)",
    "Eye (R)",
    "Eyebrow (L)",
    "Eyebrow (R)",
    "Ear (L)",
    "Ear (R)",
    "Mouth",
]


def _find_mutation_table(raw: bytes) -> int:
    size = 16 + 14 * 20
    limit = len(raw) - size
    for base in range(limit + 1):
        scale = struct.unpack_from("<f", raw, base)[0]
        if not (0.05 <= scale <= 20.0):
            continue
        coat = struct.unpack_from("<I", raw, base + 4)[0]
        if coat == 0 or coat > 20_000:
            continue
        t1 = struct.unpack_from("<I", raw, base + 8)[0]
        if t1 > 500:
            continue
        t2 = struct.unpack_from("<I", raw, base + 12)[0]
        if t2 != 0xFFFF_FFFF and t2 > 5_000:
            continue
        matches = sum(
            1
            for i in range(14)
            if struct.unpack_from("<I", raw, base + 16 + i * 20 + 4)[0] in (coat, 0)
        )
        if matches >= 10:
            return base
    return -1


def _read_visual_mutations(raw: bytes) -> list[str]:
    base = _find_mutation_table(raw)
    if base == -1:
        return []
    out: list[str] = []
    for i in range(14):
        slot_id = struct.unpack_from("<I", raw, base + 16 + i * 20)[0]
        if slot_id >= 300:
            name = VISUAL_MUT_NAMES[i] if i < len(VISUAL_MUT_NAMES) else f"Mutation{i+1}"
            out.append(f"{name} Mutation")
    return out


def parse_trait_fallback(raw: bytes) -> dict[str, list[str]]:
    """
    Fallback parser for string traits used in battle/genetics UI:
    - abilities
    - mutations (visual + passive)
    - disorders
    """
    r = BinaryReader(raw)
    run_start = -1
    curr = 0
    scan_end = max(0, len(raw) - 19)
    for i in range(curr, scan_end):
        lo = struct.unpack_from("<I", raw, i)[0]
        hi = struct.unpack_from("<I", raw, i + 4)[0]
        if hi != 0 or not (1 <= lo <= 96):
            continue
        try:
            cand = raw[i + 8 : i + 8 + lo].decode("ascii")
        except Exception:
            continue
        if cand == "DefaultMove":
            run_start = i
            break

    if run_start == -1:
        return {"abilities": [], "mutations": [], "disorders": []}

    r.seek(run_start)
    run_items: list[str] = []
    for _ in range(32):
        saved = r.pos
        item = r.str()
        if item is None or not IDENT_RE.match(item):
            r.seek(saved)
            break
        run_items.append(item)

    abilities = [x for x in run_items[1:6] if _valid_str(x)]

    passives: list[str] = []
    disorders: list[str] = []
    if len(run_items) > 10 and _valid_str(run_items[10]):
        passives.append(run_items[10])

    try:
        _ = r.u32()  # passive1 tier
    except Exception:
        pass

    for idx in range(3):
        saved = r.pos
        item = r.str()
        if item is None or not IDENT_RE.match(item) or not _valid_str(item):
            r.seek(saved)
            break
        if idx == 0:
            passives.append(item)
        else:
            disorders.append(item)
        try:
            _ = r.u32()  # tier
        except Exception:
            pass

    vis = _read_visual_mutations(raw)
    mutations = vis + passives

    def dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            key = item.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    return {
        "abilities": dedupe(abilities),
        "mutations": dedupe(mutations),
        "disorders": dedupe(disorders),
    }


def open_save_db(path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def iter_cats_from_save(path: str):
    conn = open_save_db(path)
    try:
        cur = conn.execute("SELECT key, data FROM cats")
        for key, blob in cur:
            yield int(key), blob
    finally:
        conn.close()


def _parse_house_keys(conn: sqlite3.Connection) -> set[int]:
    row = conn.execute("SELECT data FROM files WHERE key = 'house_state'").fetchone()
    if not row or len(row[0]) < 8:
        return set()
    data = row[0]
    count = struct.unpack_from("<I", data, 4)[0]
    pos = 8
    out: set[int] = set()
    for _ in range(count):
        if pos + 8 > len(data):
            break
        cat_key = struct.unpack_from("<I", data, pos)[0]
        pos += 8
        room_len = struct.unpack_from("<I", data, pos)[0]
        pos += 8
        if room_len > 0:
            pos += room_len
        pos += 24
        if cat_key:
            out.add(int(cat_key))
    return out


def _parse_adventure_keys(conn: sqlite3.Connection) -> set[int]:
    out: set[int] = set()
    try:
        row = conn.execute("SELECT data FROM files WHERE key = 'adventure_state'").fetchone()
        if not row or len(row[0]) < 8:
            return out
        data = row[0]
        count = struct.unpack_from("<I", data, 4)[0]
        pos = 8
        for _ in range(count):
            if pos + 8 > len(data):
                break
            val = struct.unpack_from("<Q", data, pos)[0]
            pos += 8
            cat_key = (val >> 32) & 0xFFFF_FFFF
            if cat_key:
                out.add(int(cat_key))
    except Exception:
        return out
    return out


def get_alive_key_sets(path: str) -> tuple[set[int], set[int]]:
    conn = open_save_db(path)
    try:
        house = _parse_house_keys(conn)
        adventure = _parse_adventure_keys(conn)
        return house, adventure
    finally:
        conn.close()
