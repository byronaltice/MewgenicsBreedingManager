"""Parse Mewgenics ability GON files into an ability_name -> icon-metadata map.

Outputs ``<icons_dir>/ability_icon_map.json``. Each ability has:
    animation:            sprite frame name in ability_icons.swf / ui.swf (or None)
    ability_icon_override: redirect to another ability's icon (one hop resolved)
    type_icon:            badge name (e.g. "defense", "attack")
    icon_shell_frame:     frame name on the icon-shell sprite

GON syntax used here is a recursive brace-delimited block format. We don't
need a full parser — only top-level ability blocks and their ``meta`` and
``graphics`` sub-blocks.
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from .gpak_reader import GpakReader, find_gpak_in

_ABILITIES_INTERNAL_PREFIX = "data/abilities/"
_GON_SUFFIX = ".gon"
_ICON_MAP_FILENAME = "ability_icon_map.json"

# Tokenize identifiers, braces, quoted strings, and bare values.
_TOKEN_RE = re.compile(
    r"""
    "([^"]*)"               # quoted string  (group 1)
    | (\{|\}|\[|\])         # bracket/brace  (group 2)
    | (//[^\n]*)            # line comment   (group 3)
    | ([^\s{}\[\],]+)       # bare token     (group 4) — comma also a separator
    """,
    re.VERBOSE,
)


def _tokenize(text: str):
    """Yield tokens. We treat ``[``/``]`` as braces of a separate kind so
    array literals don't break the block parser. Commas are skipped as
    whitespace inside array literals.
    """
    for m in _TOKEN_RE.finditer(text):
        quoted, bracket, comment, bare = m.groups()
        if comment is not None:
            continue
        if quoted is not None:
            yield ("str", quoted)
        elif bracket is not None:
            if bracket in ("{", "}"):
                yield ("brace", bracket)
            else:
                yield ("array", bracket)
        elif bare is not None:
            yield ("tok", bare)


def _parse_block(tokens, start_idx: int) -> tuple[dict, int]:
    """Parse a brace-delimited block starting at tokens[start_idx] == '{'.

    Returns (block_dict, next_idx). Block dict maps key -> str | dict | list.
    Repeated keys are coalesced into a list.
    """
    assert tokens[start_idx] == ("brace", "{")
    idx = start_idx + 1
    out: dict = {}

    while idx < len(tokens):
        tok = tokens[idx]
        if tok == ("brace", "}"):
            return out, idx + 1

        # Expect a key token.
        if tok[0] != "tok" and tok[0] != "str":
            idx += 1
            continue
        key = tok[1]
        idx += 1
        if idx >= len(tokens):
            break

        next_tok = tokens[idx]
        if next_tok == ("brace", "{"):
            sub, idx = _parse_block(tokens, idx)
            _store(out, key, sub)
        elif next_tok == ("array", "["):
            arr, idx = _parse_array(tokens, idx)
            _store(out, key, arr)
        elif next_tok[0] in ("str", "tok"):
            _store(out, key, next_tok[1])
            idx += 1
        else:
            # Unexpected token — skip it without consuming structural braces.
            idx += 1

    return out, idx


def _parse_array(tokens, start_idx: int) -> tuple[list, int]:
    """Parse a ``[ ... ]`` array literal. Returns (list, next_idx).

    Treats each element as a primitive (string/bare token) or a nested
    block/array. Used for fields like ``elements [ Electric Holy ]``.
    """
    assert tokens[start_idx] == ("array", "[")
    idx = start_idx + 1
    out: list = []
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == ("array", "]"):
            return out, idx + 1
        if tok == ("brace", "{"):
            sub, idx = _parse_block(tokens, idx)
            out.append(sub)
        elif tok == ("array", "["):
            sub, idx = _parse_array(tokens, idx)
            out.append(sub)
        elif tok[0] in ("str", "tok"):
            out.append(tok[1])
            idx += 1
        else:
            idx += 1
    return out, idx


def _store(block: dict, key: str, value):
    if key in block:
        existing = block[key]
        if isinstance(existing, list):
            existing.append(value)
        else:
            block[key] = [existing, value]
    else:
        block[key] = value


def _parse_gon_text(text: str) -> dict[str, dict]:
    """Parse top-level ability blocks. Returns {ability_name: block_dict}."""
    tokens = list(_tokenize(text))
    idx = 0
    abilities: dict[str, dict] = {}
    while idx < len(tokens):
        tok = tokens[idx]
        if tok[0] in ("tok", "str") and idx + 1 < len(tokens) and tokens[idx + 1] == ("brace", "{"):
            name = tok[1]
            block, idx = _parse_block(tokens, idx + 1)
            abilities[name] = block
        else:
            idx += 1
    return abilities


def _extract_icon_info(block: dict, name: str, all_abilities: dict[str, dict]) -> dict:
    """Pull animation / type_icon / icon_shell_frame / ability_icon override.

    Walks ``variant_of`` inheritance one level so child abilities pick up
    parent graphics when they don't define their own.
    """
    visited = set()
    current_block = block
    current_name = name

    def field(b: dict, *path: str) -> Optional[str]:
        node = b
        for key in path:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node if isinstance(node, str) else None

    animation = field(current_block, "graphics", "animation")
    ability_icon_override = field(current_block, "meta", "ability_icon")
    type_icon = field(current_block, "meta", "type_icon")
    icon_shell_frame = field(current_block, "meta", "icon_shell_frame")

    # Inherit from variant_of parent if missing.
    while True:
        if not isinstance(current_block, dict):
            break
        parent_name = current_block.get("variant_of")
        if not isinstance(parent_name, str) or parent_name in visited:
            break
        visited.add(parent_name)
        parent_block = all_abilities.get(parent_name)
        if not isinstance(parent_block, dict):
            break
        if animation is None:
            animation = field(parent_block, "graphics", "animation")
        if ability_icon_override is None:
            ability_icon_override = field(parent_block, "meta", "ability_icon")
        if type_icon is None:
            type_icon = field(parent_block, "meta", "type_icon")
        if icon_shell_frame is None:
            icon_shell_frame = field(parent_block, "meta", "icon_shell_frame")
        current_block = parent_block

    return {
        "animation": animation,
        "ability_icon_override": ability_icon_override,
        "type_icon": type_icon,
        "icon_shell_frame": icon_shell_frame,
    }


def build_ability_icon_map(install_path: str, icons_dir: str) -> dict[str, dict]:
    """Parse every abilities GON and write ability_icon_map.json.

    Resolves one hop of ``meta.ability_icon`` overrides — if A redirects to
    B, A's resolved ``animation`` is B's ``animation``. Returns the in-memory
    map for callers that want it.
    """
    gpak = find_gpak_in(install_path)
    if not gpak:
        raise FileNotFoundError(
            f"resources.gpak not found under install path: {install_path}"
        )

    raw_abilities: dict[str, dict] = {}
    with GpakReader(gpak) as reader:
        gon_names = sorted(
            name for name in reader.iter_prefix(_ABILITIES_INTERNAL_PREFIX)
            if name.endswith(_GON_SUFFIX)
        )
        for internal_name in gon_names:
            try:
                blob = reader.read(internal_name)
            except KeyError:
                continue
            text = blob.decode("utf-8", errors="replace")
            parsed = _parse_gon_text(text)
            # Later files don't override earlier (ability names are globally
            # unique in this game's data); fall back to update().
            for name, block in parsed.items():
                if name not in raw_abilities:
                    raw_abilities[name] = block

    # First pass: extract raw icon info per ability.
    raw_info: dict[str, dict] = {
        name: _extract_icon_info(block, name, raw_abilities)
        for name, block in raw_abilities.items()
    }

    # Second pass: resolve one hop of ability_icon_override.
    resolved: dict[str, dict] = {}
    for name, info in raw_info.items():
        override = info["ability_icon_override"]
        if override and override in raw_info:
            target = raw_info[override]
            resolved[name] = {
                "animation": target.get("animation") or info.get("animation"),
                "ability_icon_override": override,
                "type_icon": info.get("type_icon") or target.get("type_icon"),
                "icon_shell_frame": info.get("icon_shell_frame") or target.get("icon_shell_frame"),
            }
        else:
            resolved[name] = info

    out_path = os.path.join(icons_dir, _ICON_MAP_FILENAME)
    os.makedirs(icons_dir, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2, sort_keys=True)

    return resolved


def load_ability_icon_map(icons_dir: str) -> dict[str, dict]:
    path = os.path.join(icons_dir, _ICON_MAP_FILENAME)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
