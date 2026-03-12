#!/usr/bin/env python3
"""
Discover mapping quality for set-like traits:
  - abilities
  - mutations
  - disorders

It scans each raw blob for length-prefixed ASCII identifier strings and compares
token presence against manual labels.
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import struct
from collections import Counter, defaultdict

from common import init_db, norm_path, warn


IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def normalize_token(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.strip().lower())


def parse_label_set(value: str) -> set[str]:
    if not value:
        return set()
    parts = re.split(r"[,\n;|]+", value)
    return {normalize_token(p) for p in parts if normalize_token(p)}


def extract_ascii_identifiers(raw: bytes, max_len: int = 96) -> set[str]:
    """
    Greedy scanner for little-endian [u64 length][ASCII bytes] tokens.
    Mirrors the game's string encoding style used in many save sections.
    """
    out: set[str] = set()
    n = len(raw)
    if n < 9:
        return out

    for i in range(0, n - 8):
        lo = struct.unpack_from("<I", raw, i)[0]
        hi = struct.unpack_from("<I", raw, i + 4)[0]
        if hi != 0:
            continue
        if lo <= 0 or lo > max_len:
            continue
        end = i + 8 + lo
        if end > n:
            continue
        try:
            s = raw[i + 8 : end].decode("ascii")
        except Exception:
            continue
        if IDENT_RE.match(s):
            out.add(normalize_token(s))
    return out


def f1(tp: int, fp: int, fn: int) -> float:
    if tp <= 0:
        return 0.0
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Discover token mappings for abilities/mutations/disorders")
    p.add_argument("--db", default="tools/field_mapper/field_mapping.sqlite", help="SQLite DB path")
    p.add_argument(
        "--trait",
        required=True,
        choices=["abilities", "mutations", "disorders"],
        help="Set-like trait to analyze",
    )
    p.add_argument("--min-rows", type=int, default=20, help="Minimum labeled rows required")
    p.add_argument("--min-token-freq", type=int, default=3, help="Ignore rare observed tokens below this frequency")
    p.add_argument("--min-tp", type=int, default=3, help="Minimum true-positive rows for a token pair")
    p.add_argument("--top-per-label", type=int, default=8, help="Top candidate tokens shown per labeled term")
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


def main() -> int:
    args = parse_args()
    db_path = norm_path(args.db)
    if not os.path.exists(db_path):
        warn(f"DB not found: {db_path}")
        return 2

    label_col = f"label_{args.trait}"
    alive_clause = "" if args.include_gone else "AND c.is_alive = 1"
    gt_clause = (
        "AND l.ground_truth_source IS NOT NULL AND TRIM(l.ground_truth_source) <> ''"
        if args.ground_truth_only
        else ""
    )

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        rows = conn.execute(
            f"""
            SELECT c.raw_blob, l.{label_col} AS label_text
            FROM cats c
            JOIN labels l ON l.save_id = c.save_id AND l.cat_db_key = c.cat_db_key
            WHERE c.raw_blob IS NOT NULL
              {alive_clause}
              {gt_clause}
              AND l.{label_col} IS NOT NULL
              AND TRIM(l.{label_col}) <> ''
            """
        ).fetchall()
    finally:
        conn.close()

    if len(rows) < args.min_rows:
        warn(f"Not enough labeled rows for {args.trait}. have={len(rows)} need>={args.min_rows}")
        return 2

    dataset = []
    token_freq: Counter[str] = Counter()
    label_freq: Counter[str] = Counter()

    for row in rows:
        raw_blob = row["raw_blob"]
        labels = parse_label_set(row["label_text"] or "")
        if not labels:
            continue
        tokens = extract_ascii_identifiers(raw_blob)
        dataset.append({"labels": labels, "tokens": tokens})
        for t in tokens:
            token_freq[t] += 1
        for l in labels:
            label_freq[l] += 1

    if len(dataset) < args.min_rows:
        warn(f"Not enough valid rows after parsing. have={len(dataset)} need>={args.min_rows}")
        return 2

    token_vocab = {t for t, c in token_freq.items() if c >= args.min_token_freq}
    label_vocab = sorted(label_freq.keys())

    print(f"[INFO] trait={args.trait} rows={len(dataset)} label_terms={len(label_vocab)} token_vocab={len(token_vocab)}")
    print("[INFO] Exact-name coverage (label token exists directly in blob token set):")

    exact_scores = []
    for label in label_vocab:
        tp = 0
        fp = 0
        fn = 0
        for row in dataset:
            has_label = label in row["labels"]
            has_token = label in row["tokens"]
            if has_label and has_token:
                tp += 1
            elif has_label and not has_token:
                fn += 1
            elif (not has_label) and has_token:
                fp += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        score = f1(tp, fp, fn)
        exact_scores.append((score, label, tp, precision, recall))
    exact_scores.sort(reverse=True)

    print("label_term                      f1      tp   precision  recall")
    for score, label, tp, precision, recall in exact_scores[: min(40, len(exact_scores))]:
        print(f"{label[:28]:<28}  {score:0.4f}  {tp:>4}   {precision:0.4f}    {recall:0.4f}")

    print("\n[INFO] Best token candidates per labeled term:")
    for label in label_vocab:
        candidates = []
        for token in token_vocab:
            tp = 0
            fp = 0
            fn = 0
            for row in dataset:
                has_label = label in row["labels"]
                has_token = token in row["tokens"]
                if has_label and has_token:
                    tp += 1
                elif has_label and not has_token:
                    fn += 1
                elif (not has_label) and has_token:
                    fp += 1
            if tp < args.min_tp:
                continue
            score = f1(tp, fp, fn)
            if score <= 0:
                continue
            precision = tp / (tp + fp) if (tp + fp) else 0.0
            recall = tp / (tp + fn) if (tp + fn) else 0.0
            candidates.append((score, token, tp, precision, recall))

        if not candidates:
            continue

        candidates.sort(reverse=True)
        print(f"\nlabel: {label}   rows={label_freq[label]}")
        print("  token                         f1      tp   precision  recall")
        for score, token, tp, precision, recall in candidates[: args.top_per_label]:
            print(f"  {token[:28]:<28}  {score:0.4f}  {tp:>4}   {precision:0.4f}    {recall:0.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
