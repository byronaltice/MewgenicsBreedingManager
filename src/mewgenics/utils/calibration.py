"""Calibration data load/save, trait overrides, and gender learning."""
import os
import csv
import json
from typing import Optional

from PySide6.QtGui import QColor

from save_parser import Cat

from mewgenics.utils.paths import _calibration_path, _gender_overrides_path


_CALIBRATION_TRAIT_OPTIONS = {
    "aggression": ("average", "high", "low"),
    "libido": ("average", "high", "low"),
    "inbredness": ("not", "slightly", "moderately", "highly", "extremely"),
}

_CALIBRATION_TRAIT_NUMERIC = {
    "aggression": {"low": 0.0, "average": 0.5, "high": 1.0},
    "libido": {"low": 0.0, "average": 0.5, "high": 1.0},
    "inbredness": {"not": 0.0, "slightly": 0.175, "moderately": 0.375, "highly": 0.55, "extremely": 0.85},
}

_TRAIT_LEVEL_COLORS = {
    "low": QColor(70, 150, 90),
    "not": QColor(70, 150, 90),
    "average": QColor(185, 145, 60),
    "slightly": QColor(185, 145, 60),
    "high": QColor(175, 80, 80),
    "moderately": QColor(175, 80, 80),
    "highly": QColor(200, 50, 50),
    "extremely": QColor(235, 35, 35),
    "low to average": QColor(128, 148, 74),
    "average to high": QColor(180, 112, 70),
    "not to slightly": QColor(128, 148, 74),
    "slightly to moderately": QColor(128, 148, 74),
    "moderately to highly": QColor(180, 112, 70),
}


def _safe_float(v):
    try:
        return float(v)
    except Exception:
        return None


def _normalize_override_gender(value: Optional[str]) -> str:
    g = (value or "").strip().lower()
    if g in ("male", "m") or g.startswith("male"):
        return "male"
    if g in ("female", "f") or g.startswith("female"):
        return "female"
    if g in ("?", "unknown") or g.startswith("spidercat"):
        return "?"
    return ""


def _normalize_trait_override(field: str, value) -> str:
    options = _CALIBRATION_TRAIT_OPTIONS.get(field)
    if not options:
        return ""
    txt = str(value or "").strip().lower()
    if not txt:
        return ""
    if txt in options:
        return txt
    if field in ("aggression", "libido"):
        aliases = {"avg": "average", "medium": "average", "med": "average", "mid": "average"}
        mapped = aliases.get(txt, "")
        if mapped:
            return mapped
    if field == "inbredness":
        aliases = {"none": "not", "no": "not", "medium": "slightly", "med": "slightly",
                   "high": "highly", "extreme": "extremely", "extremely": "extremely"}
        mapped = aliases.get(txt, "")
        if mapped:
            return mapped
    return ""


def _trait_numeric_override(field: str, value):
    label = _normalize_trait_override(field, value)
    if not label:
        return None
    return _CALIBRATION_TRAIT_NUMERIC[field][label]


def _trait_label_from_value(field: str, value) -> str:
    label = _normalize_trait_override(field, value)
    if label:
        return label
    n = _safe_float(value)
    if n is None:
        return ""
    if field in ("aggression", "libido"):
        if n < 0.30:
            return "low"
        if n > 0.70:
            return "high"
        return "average"
    if field == "inbredness":
        if n <= 0.10:
            return "not"
        if n <= 0.25:
            return "slightly"
        if n <= 0.50:
            return "moderately"
        if n <= 0.80:
            return "highly"
        return "extremely"
    return ""


def _trait_level_color(text: str) -> QColor:
    return _TRAIT_LEVEL_COLORS.get(str(text or "").strip().lower(), QColor(80, 80, 95))


def _load_calibration_data(save_path: str) -> dict:
    path = _calibration_path(save_path)
    if not os.path.exists(path):
        return {"version": 1, "overrides": {}, "gender_token_map": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"version": 1, "overrides": {}, "gender_token_map": {}}
        data.setdefault("version", 1)
        data.setdefault("overrides", {})
        data.setdefault("gender_token_map", {})
        if not isinstance(data["overrides"], dict):
            data["overrides"] = {}
        if not isinstance(data["gender_token_map"], dict):
            data["gender_token_map"] = {}
        return data
    except Exception:
        return {"version": 1, "overrides": {}, "gender_token_map": {}}


def _save_calibration_data(save_path: str, data: dict) -> bool:
    path = _calibration_path(save_path)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=True)
        return True
    except Exception:
        return False


def _learn_gender_token_map(cats: list[Cat], overrides: dict) -> dict[str, str]:
    counts: dict[str, dict[str, int]] = {}
    for cat in cats:
        if getattr(cat, "gender_source", "") != "token_fallback":
            continue
        token = (getattr(cat, "gender_token", "") or "").strip().lower()
        uid = (cat.unique_id or "").strip().lower()
        if not token or not uid:
            continue
        ov = overrides.get(uid)
        if not isinstance(ov, dict):
            continue
        g = _normalize_override_gender(ov.get("gender"))
        if not g:
            continue
        bucket = counts.setdefault(token, {})
        bucket[g] = bucket.get(g, 0) + 1

    out: dict[str, str] = {}
    for token, bucket in counts.items():
        total = sum(bucket.values())
        if total <= 0:
            continue
        top_gender, top_count = max(bucket.items(), key=lambda kv: kv[1])
        if top_count / total >= 0.80:
            out[token] = top_gender
    return out


def _apply_calibration_data(data: dict, cats: list[Cat]) -> tuple[int, int, int]:
    """
    Apply calibration payload to cats in memory.
    Returns (explicit_rows_applied, token_rows_applied, override_rows_present).
    """
    overrides = data.get("overrides", {}) if isinstance(data, dict) else {}
    token_map = data.get("gender_token_map", {}) if isinstance(data, dict) else {}
    if not isinstance(overrides, dict):
        overrides = {}
    if not isinstance(token_map, dict):
        token_map = {}

    norm_token_map: dict[str, str] = {}
    for k, v in token_map.items():
        token = str(k).strip().lower()
        g = _normalize_override_gender(v)
        if token and g:
            norm_token_map[token] = g

    token_rows_applied = 0
    for cat in cats:
        if getattr(cat, "status", "") == "Gone":
            continue
        if getattr(cat, "gender_source", "") != "token_fallback":
            continue
        token = (getattr(cat, "gender_token", "") or "").strip().lower()
        mapped = norm_token_map.get(token, "")
        if mapped and cat.gender != mapped:
            cat.gender = mapped
            token_rows_applied += 1

    explicit_rows_applied = 0
    for cat in cats:
        if getattr(cat, "status", "") == "Gone":
            continue
        uid = (cat.unique_id or "").strip().lower()
        ov = overrides.get(uid)
        if not isinstance(ov, dict):
            continue

        touched = False
        g = _normalize_override_gender(ov.get("gender"))
        if g:
            if cat.gender != g:
                cat.gender = g
            touched = True

        for field in ("age", "aggression", "libido", "inbredness"):
            if field == "age":
                val = _safe_float(ov.get(field))
            else:
                val = _trait_numeric_override(field, ov.get(field))
            if val is not None:
                setattr(cat, field, val)
                touched = True

        sex = ov.get("sexuality", "")
        if sex in ("bi", "gay", "straight"):
            cat.sexuality = sex
            touched = True

        base_stats_override = ov.get("base_stats")
        if isinstance(base_stats_override, dict):
            for stat_name, stat_val in base_stats_override.items():
                if stat_name in cat.base_stats:
                    try:
                        val = int(stat_val)
                        if 0 <= val <= 20:
                            cat.base_stats[stat_name] = val
                            touched = True
                    except (ValueError, TypeError):
                        pass

        if touched:
            explicit_rows_applied += 1

    return explicit_rows_applied, token_rows_applied, len(overrides)


def _apply_calibration(save_path: str, cats: list[Cat]) -> tuple[int, int, int]:
    data = _load_calibration_data(save_path)
    return _apply_calibration_data(data, cats)


def _load_gender_overrides(save_path: str, cats: list[Cat]) -> tuple[int, int]:
    """
    Apply manual gender overrides from sidecar CSV.
    Returns (applied, rows_read).
    """
    path = _gender_overrides_path(save_path)
    if not os.path.exists(path):
        return 0, 0

    by_uid: dict[str, Cat] = {str(c.unique_id).strip().lower(): c for c in cats if c.unique_id}
    by_name: dict[str, list[Cat]] = {}
    for c in cats:
        key = (c.name or "").strip().lower()
        if key:
            by_name.setdefault(key, []).append(c)

    applied = 0
    rows_read = 0
    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                return 0, 0

            for row in reader:
                rows_read += 1
                g = _normalize_override_gender(row.get("gender"))
                if not g:
                    continue

                uid = (row.get("unique_id") or "").strip().lower()
                name = (row.get("name") or "").strip().lower()

                target: Optional[Cat] = None
                if uid and uid in by_uid:
                    target = by_uid[uid]
                elif name:
                    matches = by_name.get(name, [])
                    if len(matches) == 1:
                        target = matches[0]

                if target is None:
                    continue

                if target.gender != g:
                    target.gender = g
                applied += 1
    except Exception:
        return 0, 0

    return applied, rows_read
