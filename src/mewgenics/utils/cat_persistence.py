"""Blacklist, must-breed, pinned, and tags load/save."""
import os
import json

from save_parser import Cat

from mewgenics.utils.paths import _blacklist_path, _must_breed_path, _pinned_path, _tags_path
from mewgenics.utils.tags import _TAG_DEFS, _cat_tags


def _save_blacklist(save_path: str, cats: list[Cat]):
    """Save blacklisted cat unique IDs to file."""
    blacklist_file = _blacklist_path(save_path)
    blacklisted_uids = [c.unique_id for c in cats if c.is_blacklisted]
    try:
        with open(blacklist_file, 'w') as f:
            f.write('\n'.join(blacklisted_uids))
    except Exception:
        pass


def _load_blacklist(save_path: str, cats: list[Cat]):
    """Load blacklist and mark cats accordingly."""
    blacklist_file = _blacklist_path(save_path)
    if not os.path.exists(blacklist_file):
        return
    try:
        with open(blacklist_file, 'r') as f:
            blacklisted_uids = set(line.strip() for line in f if line.strip())
        for cat in cats:
            cat.is_blacklisted = cat.unique_id in blacklisted_uids
    except Exception:
        pass


def _save_must_breed(save_path: str, cats: list[Cat]):
    """Save must-breed cat unique IDs to file."""
    must_breed_file = _must_breed_path(save_path)
    must_breed_uids = [c.unique_id for c in cats if c.must_breed]
    try:
        with open(must_breed_file, 'w') as f:
            f.write('\n'.join(must_breed_uids))
    except Exception:
        pass


def _load_must_breed(save_path: str, cats: list[Cat]):
    """Load must-breed list and mark cats accordingly."""
    must_breed_file = _must_breed_path(save_path)
    if not os.path.exists(must_breed_file):
        return
    try:
        with open(must_breed_file, 'r') as f:
            must_breed_uids = set(line.strip() for line in f if line.strip())
        for cat in cats:
            cat.must_breed = cat.unique_id in must_breed_uids
    except Exception:
        pass


def _save_pinned(save_path: str, cats: list[Cat]):
    """Save pinned cat unique IDs to file."""
    pinned_file = _pinned_path(save_path)
    pinned_uids = [c.unique_id for c in cats if c.is_pinned]
    try:
        with open(pinned_file, 'w') as f:
            f.write('\n'.join(pinned_uids))
    except Exception:
        pass


def _load_pinned(save_path: str, cats: list[Cat]):
    """Load pinned list and mark cats accordingly."""
    pinned_file = _pinned_path(save_path)
    if not os.path.exists(pinned_file):
        return
    try:
        with open(pinned_file, 'r') as f:
            pinned_uids = set(line.strip() for line in f if line.strip())
        for cat in cats:
            cat.is_pinned = cat.unique_id in pinned_uids
    except Exception:
        pass


def _save_tags(save_path: str, cats: list[Cat]):
    """Save cat tag assignments to JSON sidecar."""
    tags_file = _tags_path(save_path)
    valid_ids = {td["id"] for td in _TAG_DEFS}
    data = {}
    for c in cats:
        tags = [t for t in _cat_tags(c) if t in valid_ids]
        if tags:
            data[c.unique_id] = tags
    try:
        with open(tags_file, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def _load_tags(save_path: str, cats: list[Cat]):
    """Load tag assignments from JSON sidecar and apply to cats."""
    tags_file = _tags_path(save_path)
    if not os.path.exists(tags_file):
        return
    try:
        with open(tags_file, 'r') as f:
            data = json.load(f)
        valid_ids = {td["id"] for td in _TAG_DEFS}
        for cat in cats:
            raw = data.get(cat.unique_id, [])
            cat.tags = [t for t in raw if t in valid_ids]
    except Exception:
        pass
