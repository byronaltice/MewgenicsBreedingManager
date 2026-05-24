"""Reader for Mewgenics ``resources.gpak`` archives.

The shipping gpak (Mewgenics retail build) is a flat, uncompressed archive
with a count-prefixed directory at the head of the file. Layout::

    entry_count     : u32 little-endian — number of directory entries
    directory       : ``entry_count`` records, each:
        name_len    : u16 little-endian (length in bytes of the utf-8 name)
        name        : utf-8 bytes, e.g. ``"swfs/ability_icons.swf"``
        size        : u32 little-endian (size of the entry's body in bytes)
    bodies          : raw concatenation of entry bodies, in directory order,
                      starting immediately after the directory.

There is no leading magic. Bodies are uncompressed at the wrapper level
(individual SWF entries may use SWF-internal compression — that is the SWF
parser's concern). For the shipping ~5 GB / ~19,900-entry archive the
directory is under a megabyte; we parse it eagerly and seek into the body
region on demand for ``read``/``extract``. The body region is never loaded
into memory.

Reverse-engineered against the retail ``resources.gpak`` by hashing
extracted oracles (``audio/combat_sfx.gon``, ``swfs/ability_icons.swf``)
and confirming byte-exact round-trip and that ``dir_end + sum(sizes)``
equals the file size exactly.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Iterable, Optional

# ── Format constants ──────────────────────────────────────────────────────────

_COUNT_BYTES = 4             # u32 entry count at file head
_NAME_LEN_BYTES = 2          # u16 per-entry name length
_ENTRY_SIZE_BYTES = 4        # u32 per-entry body size
_MAX_REASONABLE_NAME_LEN = 1024
_MAX_REASONABLE_ENTRY_COUNT = 10_000_000  # sanity bound against junk files


class GpakError(Exception):
    """Raised when a gpak file is malformed or cannot be opened."""


class GpakReader:
    """Lazy reader for a single ``resources.gpak`` file.

    Parses the directory eagerly (small) and exposes per-entry read/extract
    backed by ``seek``+``read`` against the still-open file handle.
    """

    def __init__(self, gpak_path: str | os.PathLike[str]) -> None:
        self._path = os.fspath(gpak_path)
        if not os.path.isfile(self._path):
            raise GpakError(f"Not a file: {self._path}")
        self._fh = open(self._path, "rb")
        try:
            self._entries: dict[str, tuple[int, int]] = {}
            self._order: list[str] = []
            self._parse_directory()
        except Exception:
            self._fh.close()
            raise

    # ── Public API ────────────────────────────────────────────────────────────

    def list_entries(self) -> list[str]:
        """Return all internal entry paths in directory order."""
        return list(self._order)

    def has(self, internal_path: str) -> bool:
        return internal_path in self._entries

    def read(self, internal_path: str) -> bytes:
        """Return the bytes of one entry. Raises ``KeyError`` if missing."""
        offset, size = self._lookup(internal_path)
        self._fh.seek(offset)
        body = self._fh.read(size)
        if len(body) != size:
            raise GpakError(
                f"Short read for {internal_path!r}: "
                f"expected {size}, got {len(body)}"
            )
        return body

    def extract(self, internal_path: str, dest: str | os.PathLike[str]) -> Path:
        """Write one entry to ``dest`` and return the destination ``Path``."""
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as out:
            out.write(self.read(internal_path))
        return dest_path

    def iter_prefix(self, prefix: str) -> Iterable[str]:
        """Yield entry names beginning with ``prefix`` in directory order."""
        for name in self._order:
            if name.startswith(prefix):
                yield name

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.close()

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "GpakReader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # ── Internals ─────────────────────────────────────────────────────────────

    def _lookup(self, internal_path: str) -> tuple[int, int]:
        if internal_path not in self._entries:
            raise KeyError(internal_path)
        return self._entries[internal_path]

    def _parse_directory(self) -> None:
        fh = self._fh
        fh.seek(0)
        count_buf = fh.read(_COUNT_BYTES)
        if len(count_buf) < _COUNT_BYTES:
            raise GpakError(f"{self._path}: file too small for header")
        (entry_count,) = struct.unpack("<I", count_buf)
        if entry_count == 0 or entry_count > _MAX_REASONABLE_ENTRY_COUNT:
            raise GpakError(
                f"{self._path}: implausible entry count {entry_count}"
            )

        directory: list[tuple[str, int]] = []
        for i in range(entry_count):
            len_buf = fh.read(_NAME_LEN_BYTES)
            if len(len_buf) < _NAME_LEN_BYTES:
                raise GpakError(
                    f"{self._path}: truncated name length at entry {i}"
                )
            (name_len,) = struct.unpack("<H", len_buf)
            if name_len == 0 or name_len > _MAX_REASONABLE_NAME_LEN:
                raise GpakError(
                    f"{self._path}: implausible name length {name_len} "
                    f"at entry {i}"
                )
            name_bytes = fh.read(name_len)
            if len(name_bytes) < name_len:
                raise GpakError(
                    f"{self._path}: truncated entry name at entry {i}"
                )
            size_buf = fh.read(_ENTRY_SIZE_BYTES)
            if len(size_buf) < _ENTRY_SIZE_BYTES:
                raise GpakError(
                    f"{self._path}: truncated entry size at entry {i}"
                )
            (entry_size,) = struct.unpack("<I", size_buf)
            try:
                name = name_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GpakError(
                    f"{self._path}: non-utf8 entry name {name_bytes!r} "
                    f"at entry {i}"
                ) from exc
            directory.append((name, entry_size))

        body_start = fh.tell()
        cursor = body_start
        for name, size in directory:
            self._entries[name] = (cursor, size)
            self._order.append(name)
            cursor += size


def find_gpak_in(install_path: str) -> Optional[str]:
    """Return the path to ``resources.gpak`` inside ``install_path``, or None.

    Convenience helper for callers that store the install root rather than
    the gpak file path itself.
    """
    if not install_path or not os.path.isdir(install_path):
        return None
    candidate = os.path.join(install_path, "resources.gpak")
    return candidate if os.path.isfile(candidate) else None
