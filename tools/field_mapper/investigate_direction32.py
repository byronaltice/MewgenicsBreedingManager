"""
Direction 32 - Search executable/resources for defect strings and constants.

This is a fast first pass before targeted Ghidra decompilation. It scans:

  test-runtimes/Mewgenics/Mewgenics.exe
  test-runtimes/Mewgenics/resources.gpak

for defect-related strings plus the little-endian constants for -2 /
0xFFFFFFFE. For Mewgenics.exe hits, raw file offsets are mapped to virtual
addresses using the PE section table so Ghidra follow-up can jump directly to
candidate addresses.
"""
from __future__ import annotations

import mmap
import struct
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "test-runtimes" / "Mewgenics"
EXE = RUNTIME / "Mewgenics.exe"
GPAK = RUNTIME / "resources.gpak"
OUT = Path(__file__).parent / "direction32_results.txt"

TERMS = [
    "birth_defect",
    "tag birth_defect",
    "MUTATION_EYES_M2_DESC",
    "MUTATION_EYEBROWS_M2_DESC",
    "MUTATION_EARS_M2_DESC",
    "blind",
    "no eyes",
    "no eyebrows",
    "no ears",
    "cha -2",
    "dex -2",
]

CONSTANT_PATTERNS = {
    "u32 0xFFFFFFFE / -2": bytes.fromhex("fe ff ff ff"),
    "i32 -2 plus zero": bytes.fromhex("fe ff ff ff 00 00 00 00"),
}

MAX_HITS_PER_PATTERN = 40
CONTEXT_BYTES = 80
CHUNK_SIZE = 16 * 1024 * 1024

_lines: list[str] = []


@dataclass(frozen=True)
class PeSection:
    name: str
    virtual_address: int
    virtual_size: int
    raw_pointer: int
    raw_size: int


def out(message: str = "") -> None:
    print(message)
    _lines.append(message)


def parse_pe_sections(path: Path) -> tuple[int, list[PeSection]]:
    data = path.read_bytes()
    pe_header_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_header_offset:pe_header_offset + 4] != b"PE\0\0":
        raise ValueError(f"{path} is not a PE file")
    coff_offset = pe_header_offset + 4
    section_count = struct.unpack_from("<H", data, coff_offset + 2)[0]
    optional_header_size = struct.unpack_from("<H", data, coff_offset + 16)[0]
    optional_header_offset = coff_offset + 20
    image_base = struct.unpack_from("<Q", data, optional_header_offset + 24)[0]
    section_table_offset = optional_header_offset + optional_header_size

    sections = []
    for section_index in range(section_count):
        section_offset = section_table_offset + section_index * 40
        raw_name = data[section_offset:section_offset + 8].split(b"\0", 1)[0]
        name = raw_name.decode("ascii", errors="replace")
        virtual_size = struct.unpack_from("<I", data, section_offset + 8)[0]
        virtual_address = struct.unpack_from("<I", data, section_offset + 12)[0]
        raw_size = struct.unpack_from("<I", data, section_offset + 16)[0]
        raw_pointer = struct.unpack_from("<I", data, section_offset + 20)[0]
        sections.append(PeSection(name, virtual_address, virtual_size, raw_pointer, raw_size))
    return image_base, sections


def raw_to_va(raw_offset: int, image_base: int, sections: list[PeSection]) -> str:
    for section in sections:
        start = section.raw_pointer
        end = start + section.raw_size
        if start <= raw_offset < end:
            rva = section.virtual_address + (raw_offset - section.raw_pointer)
            return f"0x{image_base + rva:016x} ({section.name}+0x{raw_offset - section.raw_pointer:x})"
    return "<no section>"


def format_context(blob: bytes) -> str:
    printable = []
    for byte in blob:
        if 32 <= byte <= 126:
            printable.append(chr(byte))
        else:
            printable.append(".")
    return "".join(printable)


def find_all(data: bytes, pattern: bytes) -> list[int]:
    offsets = []
    pos = data.find(pattern)
    while pos != -1 and len(offsets) < MAX_HITS_PER_PATTERN:
        offsets.append(pos)
        pos = data.find(pattern, pos + 1)
    return offsets


def scan_small_file(path: Path, patterns: dict[str, bytes], image_base: int | None = None,
                    sections: list[PeSection] | None = None) -> None:
    out(f"\n=== {path} ===")
    data = path.read_bytes()
    for label, pattern in patterns.items():
        hits = find_all(data, pattern)
        out(f"\npattern {label!r}: {len(hits)} hit(s) shown")
        for offset in hits:
            start = max(0, offset - CONTEXT_BYTES)
            end = min(len(data), offset + len(pattern) + CONTEXT_BYTES)
            location = f"file+0x{offset:x}"
            if image_base is not None and sections is not None:
                location += f" -> {raw_to_va(offset, image_base, sections)}"
            out(f"  {location}")
            out(f"    context: {format_context(data[start:end])}")


def scan_large_file(path: Path, patterns: dict[str, bytes]) -> None:
    out(f"\n=== {path} ===")
    file_size = path.stat().st_size
    overlap = max(len(pattern) for pattern in patterns.values()) + CONTEXT_BYTES
    hit_counts = {label: 0 for label in patterns}
    with path.open("rb") as handle:
        base_offset = 0
        previous_tail = b""
        while base_offset < file_size:
            chunk = handle.read(CHUNK_SIZE)
            if not chunk:
                break
            scan_data = previous_tail + chunk
            scan_base = base_offset - len(previous_tail)
            for label, pattern in patterns.items():
                pos = scan_data.find(pattern)
                while pos != -1 and hit_counts[label] < MAX_HITS_PER_PATTERN:
                    file_offset = scan_base + pos
                    context_start = max(0, pos - CONTEXT_BYTES)
                    context_end = min(len(scan_data), pos + len(pattern) + CONTEXT_BYTES)
                    out(f"  pattern {label!r} file+0x{file_offset:x}")
                    out(f"    context: {format_context(scan_data[context_start:context_end])}")
                    hit_counts[label] += 1
                    pos = scan_data.find(pattern, pos + 1)
            previous_tail = scan_data[-overlap:]
            base_offset += len(chunk)
    out("\nsummary:")
    for label, count in hit_counts.items():
        out(f"  {label!r}: {count} hit(s) shown")


def build_patterns() -> dict[str, bytes]:
    patterns = dict(CONSTANT_PATTERNS)
    for term in TERMS:
        patterns[f"utf8 {term}"] = term.encode("utf-8")
        patterns[f"utf16le {term}"] = term.encode("utf-16le")
    return patterns


def main() -> None:
    out("Direction 32 - Search executable/resources for defect strings and constants")
    patterns = build_patterns()
    image_base, sections = parse_pe_sections(EXE)
    out(f"Mewgenics.exe image_base=0x{image_base:x}")
    out("Sections:")
    for section in sections:
        out(
            f"  {section.name}: raw=0x{section.raw_pointer:x}+0x{section.raw_size:x}, "
            f"rva=0x{section.virtual_address:x}+0x{section.virtual_size:x}"
        )
    scan_small_file(EXE, patterns, image_base, sections)
    scan_large_file(GPAK, patterns)
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    out(f"\nResults written to {OUT}")


if __name__ == "__main__":
    main()
