"""Direction #9 -- Roster-wide pre-T f64 scan.

Whommie has f64[3]=0.0 and f64[6]=0.0, both unique across sampled controls.
Bud does NOT match this pattern. Test two hypotheses roster-wide:

(A) Whommie-specific pattern: cats with f64[3]==0.0 or f64[6]==0.0 correlate
    with known defect-carriers.
(B) Some other per-slot value (f64[0..7], not just the two we noticed)
    distinguishes every known defective cat from every clean cat.

Since the only confirmed defective cats we know by name are Whommie and Bud,
this is exploratory. We dump the full f64 distribution and highlight outliers.
"""
from __future__ import annotations

import sys
import struct
import sqlite3
from collections import Counter
from pathlib import Path

import lz4.block

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from save_parser import parse_save  # noqa: E402

SAVE = ROOT / "test-saves" / "steamcampaign01.sav"
OUT = Path(__file__).parent / "direction9_results.txt"

_lines: list[str] = []


def out(msg: str = "") -> None:
    print(msg)
    _lines.append(msg)


def raw_blob(conn, db_key: int) -> bytes:
    row = conn.execute("SELECT data FROM cats WHERE key=?", (db_key,)).fetchone()
    data = bytes(row[0])
    uncomp = struct.unpack_from("<I", data, 0)[0]
    return lz4.block.decompress(data[4:], uncompressed_size=uncomp)


def locate_t_start(raw: bytes, cat) -> int:
    fur = cat.body_parts["texture"]
    body = cat.body_parts["bodyShape"]
    head = cat.body_parts["headShape"]
    target = struct.pack("<I", fur)
    for i in range(0, len(raw) - 9 * 4):
        if raw[i:i + 4] == target:
            if struct.unpack_from("<I", raw, i + 3 * 4)[0] == body and \
               struct.unpack_from("<I", raw, i + 8 * 4)[0] == head:
                return i
    return -1


def main() -> None:
    out("=" * 70)
    out("Direction #9 -- Roster-wide pre-T f64 scan")
    out("=" * 70)

    save_data = parse_save(str(SAVE))
    cats = save_data.cats
    conn = sqlite3.connect(str(SAVE))

    results: list[tuple[str, int, list[float], list[bytes]]] = []
    for cat in cats:
        try:
            raw = raw_blob(conn, cat.db_key)
            t_start = locate_t_start(raw, cat)
            if t_start < 64:
                continue
            pre_t = t_start - 64
            floats = [struct.unpack_from("<d", raw, pre_t + 8 * i)[0] for i in range(8)]
            hex_vals = [raw[pre_t + 8 * i:pre_t + 8 * i + 8] for i in range(8)]
            results.append((cat.name, cat.db_key, floats, hex_vals))
        except Exception as e:
            out(f"skip {cat.name}: {e}")

    out(f"Scanned {len(results)} cats\n")

    import math

    def classify(f: float, raw_bytes: bytes) -> str:
        if raw_bytes == b"\xff" * 8:
            return "NaN_allF"
        if math.isnan(f):
            return "NaN"
        if f == 0.0:
            return "zero"
        if 0 < abs(f) < 1e-100:
            return "subnormal"
        return "normal"

    out("=" * 70)
    out("STEP 1 -- Distribution of each f64 slot")
    out("=" * 70)
    for slot in range(8):
        counter: Counter = Counter()
        for _, _, floats, hexes in results:
            counter[classify(floats[slot], hexes[slot])] += 1
        out(f"  f64[{slot}]: {dict(counter)}")
    out("")

    out("=" * 70)
    out("STEP 2 -- Cats with f64[3]==0.0 (Whommie-pattern)")
    out("=" * 70)
    zero3 = [(n, k) for n, k, f, _ in results if f[3] == 0.0 and not math.isnan(f[3])]
    out(f"  Count: {len(zero3)}")
    out(f"  Names: {[n for n, _ in zero3[:30]]}")
    out("")

    out("=" * 70)
    out("STEP 3 -- Cats with f64[6]==0.0 (Whommie-pattern)")
    out("=" * 70)
    zero6 = [(n, k) for n, k, f, _ in results if f[6] == 0.0 and not math.isnan(f[6])]
    out(f"  Count: {len(zero6)}")
    out(f"  Names: {[n for n, _ in zero6[:30]]}")
    out("")

    out("=" * 70)
    out("STEP 4 -- Cats with both f64[3]==0.0 AND f64[6]==0.0")
    out("=" * 70)
    both_zero = [(n, k) for n, k, f, _ in results if f[3] == 0.0 and f[6] == 0.0]
    out(f"  Count: {len(both_zero)}")
    out(f"  Names: {[n for n, _ in both_zero[:30]]}")
    out("")

    out("=" * 70)
    out("STEP 5 -- Cats whose f64[6] != 0.5 (the 'standard' value)")
    out("=" * 70)
    nonstandard6 = [(n, k, f[6]) for n, k, f, _ in results if f[6] != 0.5]
    out(f"  Count: {len(nonstandard6)}")
    for n, k, v in nonstandard6[:30]:
        out(f"    {n} (db_key={k}): f64[6]={v}")
    out("")

    out("=" * 70)
    out("STEP 6 -- Dump pre-T hex for Whommie and neighbors (first 30 cats with f64[6]!=0.5)")
    out("=" * 70)
    for n, k, _ in nonstandard6[:30]:
        for name, db_key, floats, hexes in results:
            if name == n and db_key == k:
                out(f"  {n}: {' '.join(h.hex() for h in hexes)}")
                break
    out("")

    conn.close()
    OUT.write_text("\n".join(_lines), encoding="utf-8")
    print(f"\n[Results written to {OUT}]")


if __name__ == "__main__":
    main()
