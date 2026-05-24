"""Reader for Mewgenics ``resources.gpak`` archives.

The gpak wrapper is a flat, uncompressed archive. Layout::

    magic           : 2 bytes, ASCII "NH"
    reserved        : 2 bytes, little-endian u16 (observed value 0)
    directory       : sequence of entries, terminated by EOF of directory:
        name_len    : little-endian u16 (length in bytes of the utf-8 name)
        name        : utf-8 bytes, e.g. "swfs/ability_icons.swf"
        size        : little-endian u32 (size of the entry's body in bytes)
    body            : raw concatenation of entry bodies, in directory order.

Bodies are stored uncompressed at the wrapper level. Individual SWF entries
may use SWF-internal compression — that is the SWF parser's concern.

The reader walks the directory once (the directory itself is small — under a
megabyte for the ~18k-entry shipped archive) and seeks into the body region
on demand for ``read``/``extract``. The 4.9 GB body is never loaded into
memory.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path
from typing import Iterable, Optional

# ── Format constants ──────────────────────────────────────────────────────────

_MAGIC = b"NH"
_HEADER_LEN = 4              # magic(2) + reserved(2)
_NAME_LEN_BYTES = 2          # u16
_ENTRY_SIZE_BYTES = 4        # u32
_MAX_REASONABLE_NAME_LEN = 1024  # any larger value indicates corruption / EOD


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
        header = fh.read(_HEADER_LEN)
        if len(header) < _HEADER_LEN or header[:2] != _MAGIC:
            raise GpakError(
                f"{self._path}: missing 'NH' magic (got {header[:2]!r})"
            )

        # Walk the directory by reading [u16 name_len][name][u32 size] until a
        # name_len of zero (or implausibly large) signals the start of the
        # body region. We compute body offsets as a running cursor that starts
        # at end-of-directory and advances by each entry's size.
        directory_entries: list[tuple[str, int]] = []
        while True:
            len_buf = fh.read(_NAME_LEN_BYTES)
            if len(len_buf) < _NAME_LEN_BYTES:
                break
            (name_len,) = struct.unpack("<H", len_buf)
            if name_len == 0 or name_len > _MAX_REASONABLE_NAME_LEN:
                # Step back; this position is the start of the body region.
                fh.seek(-_NAME_LEN_BYTES, os.SEEK_CUR)
                break
            name_bytes = fh.read(name_len)
            if len(name_bytes) < name_len:
                raise GpakError(f"{self._path}: truncated entry name")
            size_buf = fh.read(_ENTRY_SIZE_BYTES)
            if len(size_buf) < _ENTRY_SIZE_BYTES:
                raise GpakError(f"{self._path}: truncated entry size")
            (entry_size,) = struct.unpack("<I", size_buf)
            try:
                name = name_bytes.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise GpakError(
                    f"{self._path}: non-utf8 entry name {name_bytes!r}"
                ) from exc
            directory_entries.append((name, entry_size))

        body_start = fh.tell()
        cursor = body_start
        for name, size in directory_entries:
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
