"""save_writer.py — Write helpers for Mewgenics .sav files.

The .sav is a plain SQLite database (not LZ4-compressed at the file level).
Per-cat blobs inside may be LZ4-compressed, but the top-level SQLite write
used here does not touch those.

No Qt dependencies — safe to import from background threads or scripts.
"""

import logging
import shutil
import sqlite3
import struct
from datetime import datetime
from pathlib import Path

from save_parser import ROOM_KEYS

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BACKUP_DIRNAME        = "backups"
_BACKUP_RETENTION      = 20
_BACKUP_TIMESTAMP_FMT  = "%Y%m%d-%H%M%S"

# house_state blob layout constants (per record)
_HOUSE_STATE_KEY       = "house_state"
_RECORD_HEADER_BYTES   = 8   # 4-byte cat_key + 4-byte pad
_RECORD_LEN_BYTES      = 8   # 4-byte room_len + 4-byte pad
_RECORD_TAIL_BYTES     = 24  # opaque trailing bytes per record — preserve verbatim
_BLOB_HEADER_BYTES     = 4   # 4-byte unknown prefix before count
_BLOB_COUNT_BYTES      = 4   # 4-byte record count
_BLOB_PREFIX_BYTES     = _BLOB_HEADER_BYTES + _BLOB_COUNT_BYTES


# ── Backup helpers ────────────────────────────────────────────────────────────

def backup_save(save_path: str) -> Path:
    """Copy *save_path* into ``<save_dir>/backups/<name>.<timestamp>.sav``.

    Creates the backups directory if it does not exist.
    Returns the Path of the newly-created backup file.
    """
    src = Path(save_path)
    backup_dir = src.parent / _BACKUP_DIRNAME
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime(_BACKUP_TIMESTAMP_FMT)
    dest = backup_dir / f"{src.stem}.{timestamp}{src.suffix}"
    shutil.copy2(src, dest)
    logger.info("Backed up save to %s", dest)
    return dest


def prune_backups(save_path: str, keep: int = _BACKUP_RETENTION) -> None:
    """Delete the oldest backups for *save_path* so at most *keep* remain.

    Backups are matched by the original file's stem and sorted by mtime
    descending — the *keep* newest are preserved.
    """
    src = Path(save_path)
    backup_dir = src.parent / _BACKUP_DIRNAME
    if not backup_dir.is_dir():
        return
    pattern = f"{src.stem}.*{src.suffix}"
    candidates = sorted(backup_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in candidates[keep:]:
        try:
            old.unlink()
            logger.debug("Pruned old backup: %s", old)
        except OSError:
            logger.warning("Could not delete old backup: %s", old, exc_info=True)


# ── house_state reader / writer ───────────────────────────────────────────────

def read_house_state(conn: sqlite3.Connection) -> tuple[bytes, dict]:
    """Parse the ``house_state`` blob from an open SQLite connection.

    Returns ``(header_prefix, records)`` where:
    - ``header_prefix`` is the 4-byte unknown prefix before the record count.
    - ``records`` is an ordered ``dict[int, dict]`` mapping cat_key to
      ``{"room": str, "tail": bytes}`` so the 24-byte opaque tail per record
      is preserved verbatim.

    Raises ``ValueError`` on a malformed blob.
    """
    row = conn.execute(
        f"SELECT data FROM files WHERE key='{_HOUSE_STATE_KEY}'"
    ).fetchone()
    if not row or row[0] is None:
        raise ValueError(f"No {_HOUSE_STATE_KEY!r} row found in files table")

    data: bytes = row[0]
    if len(data) < _BLOB_PREFIX_BYTES:
        raise ValueError(
            f"{_HOUSE_STATE_KEY} blob too short: {len(data)} < {_BLOB_PREFIX_BYTES}"
        )

    header_prefix = data[:_BLOB_HEADER_BYTES]
    count = struct.unpack_from("<I", data, _BLOB_HEADER_BYTES)[0]
    pos = _BLOB_PREFIX_BYTES

    records: dict[int, dict] = {}
    for record_idx in range(count):
        if pos + _RECORD_HEADER_BYTES > len(data):
            raise ValueError(
                f"Truncated house_state: expected record {record_idx} at pos {pos}"
            )
        cat_key = struct.unpack_from("<I", data, pos)[0]
        pos += _RECORD_HEADER_BYTES

        if pos + _RECORD_LEN_BYTES > len(data):
            raise ValueError(
                f"Truncated house_state: room_len field missing at pos {pos}"
            )
        room_len = struct.unpack_from("<I", data, pos)[0]
        pos += _RECORD_LEN_BYTES

        if pos + room_len > len(data):
            raise ValueError(
                f"Truncated house_state: room name extends past blob at pos {pos}"
            )
        room_name = data[pos : pos + room_len].decode("ascii", errors="ignore")
        pos += room_len

        if pos + _RECORD_TAIL_BYTES > len(data):
            raise ValueError(
                f"Truncated house_state: tail bytes missing at pos {pos}"
            )
        tail = data[pos : pos + _RECORD_TAIL_BYTES]
        pos += _RECORD_TAIL_BYTES

        records[cat_key] = {"room": room_name, "tail": tail}

    return header_prefix, records


def _serialize_house_state(header_prefix: bytes, records: dict) -> bytes:
    """Re-serialize header prefix + records back into a house_state blob."""
    count = len(records)
    parts = [header_prefix, struct.pack("<I", count)]
    for cat_key, entry in records.items():
        room_bytes = entry["room"].encode("ascii")
        room_len = len(room_bytes)
        parts.append(struct.pack("<I", cat_key))
        parts.append(b"\x00" * 4)           # 4-byte pad after cat_key
        parts.append(struct.pack("<I", room_len))
        parts.append(b"\x00" * 4)           # 4-byte pad after room_len
        parts.append(room_bytes)
        parts.append(entry["tail"])          # 24-byte opaque tail verbatim
    return b"".join(parts)


def set_cat_room(save_path: str, cat_key: int, room_name: str) -> None:
    """Write *room_name* for *cat_key* into the house_state blob of *save_path*.

    Raises ``ValueError`` if *room_name* is not in ``ROOM_KEYS``, or if the
    blob is malformed.  On any error the save file is left untouched (the
    SQLite write is only committed on success).
    """
    if room_name not in ROOM_KEYS:
        raise ValueError(
            f"Invalid room name {room_name!r}. Must be one of: {ROOM_KEYS}"
        )

    conn = sqlite3.connect(save_path)
    try:
        header_prefix, records = read_house_state(conn)

        if cat_key in records:
            records[cat_key]["room"] = room_name
        else:
            # Cat not yet in house_state — append with zero tail
            records[cat_key] = {
                "room": room_name,
                "tail": b"\x00" * _RECORD_TAIL_BYTES,
            }

        new_blob = _serialize_house_state(header_prefix, records)
        conn.execute(
            f"UPDATE files SET data=? WHERE key='{_HOUSE_STATE_KEY}'",
            (new_blob,),
        )
        conn.commit()
        logger.info("Set cat %d room to %r in %s", cat_key, room_name, save_path)
    finally:
        conn.close()
