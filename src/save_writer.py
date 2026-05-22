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
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from save_parser import ROOM_KEYS
from mewgenics.utils.paths import (
    APPDATA_CONFIG_DIR, _bp_sidecar_path, _save_specific_sidecar_pairs,
)

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

_BACKUP_DIRNAME               = "backups"
_BACKUP_TIMESTAMP_FMT         = "%Y%m%d-%H%M%S"
_BACKUP_RECENT_KEEP           = 50
_BACKUP_RECENT_WINDOW         = timedelta(hours=24)
_BACKUP_DAILY_RETENTION_DAYS  = 21
_SIDECAR_BACKUP_DIRNAME       = "sidecar_backups"

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


def _select_backups_to_keep(
    entries: list[tuple[Any, float]],
) -> set[Any]:
    """Apply the 3-rule retention policy and return the handles to keep.

    *entries* must be a list of (handle, mtime) pairs, sorted newest-first.
    Returns the set of handles that satisfy at least one retention rule:

    1. **Recent window:** mtime within ``_BACKUP_RECENT_WINDOW`` (24 h) before
       the newest entry's mtime.
    2. **Top-N newest:** among the ``_BACKUP_RECENT_KEEP`` (50) newest entries.
    3. **Daily-earliest:** the entry is the earliest one on its local date, and
       that date is among the ``_BACKUP_DAILY_RETENTION_DAYS`` (21) most-recent
       distinct dates represented in *entries*.
    """
    if not entries:
        return set()

    anchor = entries[0][1]
    recent_cutoff = anchor - _BACKUP_RECENT_WINDOW.total_seconds()

    keep: set[Any] = set()

    # Rule 1: anything within 24 h before the anchor.
    for handle, mtime in entries:
        if mtime >= recent_cutoff:
            keep.add(handle)

    # Rule 2: the top-N newest.
    for handle, _mtime in entries[:_BACKUP_RECENT_KEEP]:
        keep.add(handle)

    # Rule 3: earliest entry per local date, for the most-recent 21 distinct dates.
    earliest_by_date: dict[date, tuple[Any, float]] = {}
    seen_dates_in_order: list[date] = []
    for handle, mtime in entries:  # newest first, so later iterations are older
        local_date = datetime.fromtimestamp(mtime).date()
        if local_date not in earliest_by_date:
            seen_dates_in_order.append(local_date)
        prev = earliest_by_date.get(local_date)
        if prev is None or mtime < prev[1]:
            earliest_by_date[local_date] = (handle, mtime)
    protected_dates = set(seen_dates_in_order[:_BACKUP_DAILY_RETENTION_DAYS])
    for protected_date in protected_dates:
        keep.add(earliest_by_date[protected_date][0])

    return keep


def prune_backups(save_path: str) -> None:
    """Delete backups for *save_path* that fall outside the retention policy.

    A backup is kept iff at least one of the following is true:

    1. **Recent window:** its mtime is within ``_BACKUP_RECENT_WINDOW`` (24 h)
       before the newest backup's mtime.
    2. **Top-N newest:** it is among the ``_BACKUP_RECENT_KEEP`` (50) newest
       backups by mtime.
    3. **Daily-earliest:** its local-time date is among the
       ``_BACKUP_DAILY_RETENTION_DAYS`` (21) most-recent distinct dates that
       have any backups, AND it is the earliest backup on that date.

    Anything that satisfies none of the three rules is deleted.
    """
    src = Path(save_path)
    backup_dir = src.parent / _BACKUP_DIRNAME
    if not backup_dir.is_dir():
        return

    pattern = f"{src.stem}.*{src.suffix}"
    candidates = list(backup_dir.glob(pattern))
    if not candidates:
        return

    # Pair each path with its mtime once to avoid repeated stat calls.
    entries: list[tuple[Path, float]] = [
        (p, p.stat().st_mtime) for p in candidates
    ]
    entries.sort(key=lambda pm: pm[1], reverse=True)  # newest first

    keep = _select_backups_to_keep(entries)

    for path, _mtime in entries:
        if path in keep:
            continue
        try:
            path.unlink()
            logger.debug("Pruned old backup: %s", path)
        except OSError:
            logger.warning("Could not delete old backup: %s", path, exc_info=True)


def backup_sidecars(save_path: str) -> Path:
    """Copy every present sidecar file into a timestamped backup folder.

    Copies sidecar files from their new APPDATA_CONFIG_DIR locations into
    ``APPDATA_CONFIG_DIR/sidecar_backups/<timestamp>/``, preserving filenames.
    Always includes breed_priority.json (if present) plus any of the 8
    save-specific sidecars that exist on disk.
    Skips silently if no sidecars are found (no empty folder created).
    Returns the timestamped backup folder Path.
    """
    sidecar_backup_root = Path(APPDATA_CONFIG_DIR) / _SIDECAR_BACKUP_DIRNAME

    # Collect all present sidecar files.
    sources: list[Path] = []
    bp_path = Path(_bp_sidecar_path())
    if bp_path.exists():
        sources.append(bp_path)
    for new_path, _legacy_path in _save_specific_sidecar_pairs(save_path):
        p = Path(new_path)
        if p.exists():
            sources.append(p)

    if not sources:
        return sidecar_backup_root  # nothing to back up

    timestamp = datetime.now().strftime(_BACKUP_TIMESTAMP_FMT)
    dest_dir = sidecar_backup_root / timestamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    for src_file in sources:
        try:
            shutil.copy2(src_file, dest_dir / src_file.name)
            logger.debug("Backed up sidecar %s -> %s", src_file, dest_dir)
        except OSError:
            logger.warning(
                "Could not back up sidecar %s", src_file, exc_info=True
            )

    logger.info("Sidecar backup written to %s", dest_dir)
    return dest_dir


def prune_sidecar_backups() -> None:
    """Delete sidecar backup folders that fall outside the retention policy.

    Applies the same 3-rule retention policy as ``prune_backups`` but operates
    on subfolders of ``APPDATA_CONFIG_DIR/sidecar_backups/`` rather than files.
    Pruned folders are removed with ``shutil.rmtree``.
    """
    sidecar_backup_root = Path(APPDATA_CONFIG_DIR) / _SIDECAR_BACKUP_DIRNAME
    if not sidecar_backup_root.is_dir():
        return

    candidates = [p for p in sidecar_backup_root.iterdir() if p.is_dir()]
    if not candidates:
        return

    entries: list[tuple[Path, float]] = [
        (p, p.stat().st_mtime) for p in candidates
    ]
    entries.sort(key=lambda pm: pm[1], reverse=True)  # newest first

    keep = _select_backups_to_keep(entries)

    for folder, _mtime in entries:
        if folder in keep:
            continue
        try:
            shutil.rmtree(folder)
            logger.debug("Pruned old sidecar backup folder: %s", folder)
        except Exception:
            logger.warning(
                "Could not delete sidecar backup folder: %s", folder, exc_info=True,
            )


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

    Convenience single-cat wrapper around :func:`set_cat_rooms`.
    """
    set_cat_rooms(save_path, {cat_key: room_name})


def set_cat_rooms(save_path: str, changes: dict) -> None:
    """Apply many cat→room updates atomically in one SQLite transaction.

    *changes* maps ``cat_key (int) -> room_name (str)``.  All room names must
    be in ``ROOM_KEYS``; otherwise ``ValueError`` is raised before any write.
    One connection, one blob read, one blob write, one commit — so N changes
    cost roughly the same as a single change instead of N fsyncs.
    """
    if not changes:
        return

    for room_name in changes.values():
        if room_name not in ROOM_KEYS:
            raise ValueError(
                f"Invalid room name {room_name!r}. Must be one of: {ROOM_KEYS}"
            )

    conn = sqlite3.connect(save_path)
    try:
        header_prefix, records = read_house_state(conn)

        for cat_key, room_name in changes.items():
            if cat_key in records:
                records[cat_key]["room"] = room_name
            else:
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
        logger.info(
            "Updated %d cat room%s in %s",
            len(changes), "s" if len(changes) != 1 else "", save_path,
        )
    finally:
        conn.close()
