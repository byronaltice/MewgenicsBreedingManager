#!/usr/bin/env python3
"""
Brute-force candidate field discovery from labeled cat blobs.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sqlite3
import struct
from collections import Counter, defaultdict
from typing import Callable, Optional

from common import init_db, norm_path, warn


TYPE_SIZES = {
    "u8": 1,
    "s8": 1,
    "u16": 2,
    "s16": 2,
    "u32": 4,
    "s32": 4,
    "u64": 8,
    "f32": 4,
    "f64": 8,
}


def unpack_value(blob: bytes, off: int, kind: str):
    if off < 0:
        return None
    sz = TYPE_SIZES[kind]
    if off + sz > len(blob):
        return None
    if kind == "u8":
        return blob[off]
    if kind == "s8":
        return struct.unpack_from("<b", blob, off)[0]
    if kind == "u16":
        return struct.unpack_from("<H", blob, off)[0]
    if kind == "s16":
        return struct.unpack_from("<h", blob, off)[0]
    if kind == "u32":
        return struct.unpack_from("<I", blob, off)[0]
    if kind == "s32":
        return struct.unpack_from("<i", blob, off)[0]
    if kind == "u64":
        return struct.unpack_from("<Q", blob, off)[0]
    if kind == "f32":
        v = struct.unpack_from("<f", blob, off)[0]
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    if kind == "f64":
        v = struct.unpack_from("<d", blob, off)[0]
        if math.isnan(v) or math.isinf(v):
            return None
        return float(v)
    raise ValueError(f"Unknown type: {kind}")


def normalize_gender_label(value: str) -> Optional[str]:
    s = (value or "").strip().lower()
    if not s:
        return None
    if s in {"m", "male"} or s.startswith("male"):
        return "male"
    if s in {"f", "female"} or s.startswith("female"):
        return "female"
    if s in {"?", "unknown", "spidercat"} or s.startswith("spidercat"):
        return "?"
    return None


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def pearson_corr(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) < 2:
        return None
    mx = mean(xs)
    my = mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    vx = sum(v * v for v in dx)
    vy = sum(v * v for v in dy)
    if vx <= 0 or vy <= 0:
        return None
    cov = sum(a * b for a, b in zip(dx, dy))
    return cov / math.sqrt(vx * vy)


def rank_average(values: list[float]) -> list[float]:
    idx_vals = sorted(enumerate(values), key=lambda p: p[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(idx_vals):
        j = i + 1
        while j < len(idx_vals) and idx_vals[j][1] == idx_vals[i][1]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[idx_vals[k][0]] = avg_rank
        i = j
    return ranks


def spearman_corr(xs: list[float], ys: list[float]) -> Optional[float]:
    if len(xs) < 2:
        return None
    return pearson_corr(rank_average(xs), rank_average(ys))


def categorical_score(values: list[object], labels: list[str]) -> tuple[float, float, float]:
    """
    Returns (score, accuracy, balanced_accuracy).
    """
    by_value: dict[object, Counter[str]] = defaultdict(Counter)
    for v, y in zip(values, labels):
        by_value[v][y] += 1

    value_to_label: dict[object, str] = {
        v: max(counter.items(), key=lambda p: p[1])[0]
        for v, counter in by_value.items()
    }
    pred = [value_to_label[v] for v in values]
    total = len(labels)
    correct = sum(1 for p, y in zip(pred, labels) if p == y)
    acc = correct / total if total else 0.0

    class_totals = Counter(labels)
    class_correct = Counter(y for p, y in zip(pred, labels) if p == y)
    recalls = []
    for cls, n in class_totals.items():
        if n > 0:
            recalls.append(class_correct[cls] / n)
    bal = (sum(recalls) / len(recalls)) if recalls else 0.0
    score = (acc + bal) / 2.0
    return score, acc, bal


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Brute-force discover candidate offsets for a labeled trait")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument(
        "--trait",
        required=True,
        choices=["gender", "age", "libido", "aggression", "inbredness", "gayness"],
        help="Trait to discover",
    )
    p.add_argument("--max-abs-offset", type=int, default=4096, help="Max absolute offset to scan")
    p.add_argument("--rel-start", type=int, default=-64, help="Relative scan start (name_end + rel)")
    p.add_argument("--rel-end", type=int, default=768, help="Relative scan end inclusive (name_end + rel)")
    p.add_argument("--min-samples", type=int, default=40, help="Minimum samples for a candidate")
    p.add_argument("--min-support", type=float, default=0.5, help="Minimum support ratio [0..1]")
    p.add_argument("--top", type=int, default=40, help="Top N to print")
    p.add_argument("--out-csv", default=None, help="Optional full results CSV path")
    p.add_argument(
        "--include-gone",
        action="store_true",
        help="Include gone cats (default scans alive cats only)",
    )
    p.add_argument(
        "--ground-truth-only",
        action="store_true",
        help="Use only rows tagged with ground_truth_source",
    )
    return p.parse_args()


def load_rows(
    conn: sqlite3.Connection,
    trait: str,
    include_gone: bool,
    ground_truth_only: bool,
) -> list[dict]:
    label_col = f"label_{trait}"
    alive_clause = "" if include_gone else "AND c.is_alive = 1"
    gt_clause = (
        "AND l.ground_truth_source IS NOT NULL AND TRIM(l.ground_truth_source) <> ''"
        if ground_truth_only
        else ""
    )
    sql = f"""
        SELECT c.raw_blob, c.raw_len, c.name_end_offset, l.{label_col}
        FROM cats c
        JOIN labels l ON l.save_id = c.save_id AND l.cat_db_key = c.cat_db_key
        WHERE c.raw_blob IS NOT NULL
          {alive_clause}
          {gt_clause}
          AND l.{label_col} IS NOT NULL
          AND TRIM(CAST(l.{label_col} AS TEXT)) <> ''
    """
    rows = []
    for raw_blob, raw_len, name_end_offset, label in conn.execute(sql):
        y = None
        if trait == "gender":
            y = normalize_gender_label(str(label))
        else:
            try:
                y = float(label)
                if math.isnan(y) or math.isinf(y):
                    y = None
            except Exception:
                y = None
        if y is None:
            continue
        rows.append(
            {
                "blob": raw_blob,
                "raw_len": int(raw_len),
                "name_end_offset": int(name_end_offset) if name_end_offset is not None else None,
                "label": y,
            }
        )
    return rows


def score_candidate(
    rows: list[dict],
    type_name: str,
    offset_name: str,
    offset_fn: Callable[[dict], Optional[int]],
    trait: str,
    min_samples: int,
    min_support: float,
) -> Optional[dict]:
    values = []
    labels = []
    for row in rows:
        off = offset_fn(row)
        if off is None:
            continue
        v = unpack_value(row["blob"], off, type_name)
        if v is None:
            continue
        values.append(v)
        labels.append(row["label"])

    n = len(values)
    total = len(rows)
    if n < min_samples or total <= 0:
        return None

    support = n / total
    if support < min_support:
        return None

    result = {
        "offset": offset_name,
        "type": type_name,
        "samples": n,
        "total": total,
        "support": support,
    }

    if trait == "gender":
        score, acc, bal = categorical_score(values, labels)  # type: ignore[arg-type]
        result.update(
            {
                "score": score,
                "accuracy": acc,
                "balanced_accuracy": bal,
                "unique_values": len(set(values)),
            }
        )
        return result

    xs = [float(v) for v in values]
    ys = [float(y) for y in labels]
    p = pearson_corr(xs, ys)
    s = spearman_corr(xs, ys)
    if p is None or s is None:
        return None
    result.update(
        {
            "score": abs(s),
            "pearson": p,
            "spearman": s,
            "x_min": min(xs),
            "x_max": max(xs),
        }
    )
    return result


def scan(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    if args.trait == "gender":
        types = ["u8", "u16", "u32"]
    else:
        types = ["u8", "s8", "u16", "s16", "u32", "s32", "f32", "f64"]

    results: list[dict] = []

    for off in range(args.max_abs_offset + 1):
        for t in types:
            r = score_candidate(
                rows=rows,
                type_name=t,
                offset_name=f"abs+{off}",
                offset_fn=lambda row, o=off: o,
                trait=args.trait,
                min_samples=args.min_samples,
                min_support=args.min_support,
            )
            if r is not None:
                results.append(r)

    for rel in range(args.rel_start, args.rel_end + 1):
        for t in types:
            r = score_candidate(
                rows=rows,
                type_name=t,
                offset_name=f"name_end{rel:+d}",
                offset_fn=lambda row, d=rel: None
                if row["name_end_offset"] is None
                else int(row["name_end_offset"]) + d,
                trait=args.trait,
                min_samples=args.min_samples,
                min_support=args.min_support,
            )
            if r is not None:
                results.append(r)

    results.sort(key=lambda x: (x["score"], x["support"], x["samples"]), reverse=True)
    return results


def write_csv(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    out_path = norm_path(path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    keys = sorted({k for r in rows for k in r.keys()})
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    if not os.path.exists(db_path):
        warn(f"DB not found: {db_path}")
        return 2

    conn = sqlite3.connect(db_path)
    try:
        init_db(conn)
        rows = load_rows(
            conn,
            args.trait,
            include_gone=args.include_gone,
            ground_truth_only=args.ground_truth_only,
        )
    finally:
        conn.close()

    if len(rows) < args.min_samples:
        warn(f"Not enough labeled rows for {args.trait}. have={len(rows)} need>={args.min_samples}")
        return 2

    print(f"[INFO] Loaded {len(rows)} labeled rows for trait '{args.trait}'")
    results = scan(rows, args)
    if not results:
        warn("No candidates passed thresholds.")
        return 2

    top = results[: args.top]
    if args.trait == "gender":
        print("rank  offset           type  samples  support  score    acc     bal_acc  uniq")
        for i, r in enumerate(top, 1):
            print(
                f"{i:>4}  {r['offset']:<15} {r['type']:<4}  {r['samples']:>7}  "
                f"{r['support']:.3f}   {r['score']:.4f}  {r['accuracy']:.4f}  "
                f"{r['balanced_accuracy']:.4f}   {r['unique_values']:>4}"
            )
    else:
        print("rank  offset           type  samples  support  score(|rho|)  rho      pearson")
        for i, r in enumerate(top, 1):
            print(
                f"{i:>4}  {r['offset']:<15} {r['type']:<4}  {r['samples']:>7}  "
                f"{r['support']:.3f}      {r['score']:.4f}     {r['spearman']:.4f}   {r['pearson']:.4f}"
            )

    if args.out_csv:
        write_csv(args.out_csv, results)
        print(f"[INFO] Wrote {len(results)} candidate rows to {norm_path(args.out_csv)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
