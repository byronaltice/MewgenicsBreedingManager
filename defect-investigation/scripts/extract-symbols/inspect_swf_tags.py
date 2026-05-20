"""
Inspect all tag types in SWF files to understand what content formats are used.
Also inspect SWF files looking for name_tag-related symbol names.
"""

import struct
import zlib
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from swf_parser import _parse_header, _skip_rect, _read_swf_tags, _parse_export_assets, _parse_symbol_class

# SWF Tag type -> name mapping (partial)
TAG_NAMES = {
    0: "End",
    1: "ShowFrame",
    2: "DefineShape",
    4: "PlaceObject",
    6: "DefineBits",
    7: "DefineButton",
    8: "JPEGTables",
    9: "SetBackgroundColor",
    10: "DefineFont",
    11: "DefineText",
    12: "DoAction",
    13: "DefineFontInfo",
    14: "DefineSound",
    15: "StartSound",
    17: "DefineButtonSound",
    18: "SoundStreamHead",
    19: "SoundStreamBlock",
    20: "DefineBitsLossless",
    21: "DefineBitsJPEG2",
    22: "DefineShape2",
    24: "Protect",
    25: "PathsArePostScript",
    26: "PlaceObject2",
    28: "RemoveObject2",
    32: "DefineShape3",
    33: "DefineText2",
    34: "DefineButton2",
    35: "DefineBitsJPEG3",
    36: "DefineBitsLossless2",
    37: "DefineEditText",
    39: "DefineSprite",
    43: "FrameLabel",
    45: "SoundStreamHead2",
    46: "DefineMorphShape",
    48: "DefineFont2",
    56: "ExportAssets",
    57: "ImportAssets",
    58: "EnableDebugger",
    59: "DoInitAction",
    60: "DefineVideoStream",
    61: "VideoFrame",
    62: "DefineFontInfo2",
    63: "DebugID",
    64: "EnableDebugger2",
    65: "ScriptLimits",
    66: "SetTabIndex",
    69: "FileAttributes",
    70: "PlaceObject3",
    71: "ImportAssets2",
    73: "DefineFontAlignZones",
    74: "CSMTextSettings",
    75: "DefineFont3",
    76: "SymbolClass",
    77: "Metadata",
    78: "DefineScalingGrid",
    82: "DoABC",
    83: "DefineShape4",
    84: "DefineMorphShape2",
    86: "DefineSceneAndFrameLabelData",
    87: "DefineBinaryData",
    88: "DefineFontName",
    89: "StartSound2",
    90: "DefineBitsJPEG4",
    91: "DefineFont4",
    93: "EnableTelemetry",
    94: "PlaceObject4",
}

NAME_TAG_TARGETS = [
    "str", "dex", "con", "int", "spd", "cha", "lck",
    "stimulation", "comfort", "appeal", "health", "evolution",
    "star2", "circle", "triangle", "sword", "shield2", "poop",
]


def inspect_swf(swf_path, show_all_names=False):
    with open(swf_path, "rb") as f:
        raw = f.read()

    body, version = _parse_header(raw)
    after_header = _skip_rect(body)[4:]

    tag_counts = {}
    names = {}
    define_shape_ids = []
    define_sprite_ids = []

    for tag_type, tag_data in _read_swf_tags(after_header):
        tag_name = TAG_NAMES.get(tag_type, f"Unknown_{tag_type}")
        tag_counts[tag_name] = tag_counts.get(tag_name, 0) + 1

        if tag_type == 56:  # ExportAssets
            _parse_export_assets(tag_data, names)
        elif tag_type == 76:  # SymbolClass
            _parse_symbol_class(tag_data, names)
        elif tag_type in (2, 22, 32, 83):  # DefineShape 1-4
            if len(tag_data) >= 2:
                cid = struct.unpack_from("<H", tag_data, 0)[0]
                define_shape_ids.append(cid)
        elif tag_type == 39:  # DefineSprite
            if len(tag_data) >= 2:
                cid = struct.unpack_from("<H", tag_data, 0)[0]
                define_sprite_ids.append(cid)

    print(f"\n{'='*60}")
    print(f"SWF: {os.path.basename(swf_path)}")
    print(f"  Version: {version}")
    print(f"  Tag type summary:")
    for name, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        print(f"    {name}: {count}")

    print(f"\n  Total named symbols: {len(names)}")
    print(f"  DefineShape symbols: {len(define_shape_ids)}")
    print(f"  DefineSprite symbols: {len(define_sprite_ids)}")

    # Look for name_tag related names
    matching = [(cid, name) for cid, name in names.items()
                if any(t in name.lower() for t in NAME_TAG_TARGETS)]

    if matching:
        print(f"\n  ** NAME_TAG MATCHING SYMBOLS: **")
        for cid, name in sorted(matching):
            shape = " [shape]" if cid in define_shape_ids else ""
            sprite = " [sprite]" if cid in define_sprite_ids else ""
            print(f"    {cid:4d} -> {name}{shape}{sprite}")

    if show_all_names:
        print(f"\n  All names:")
        for cid, name in sorted(names.items()):
            print(f"    {cid:4d} -> {name}")

    return names


if __name__ == "__main__":
    DEFECT_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
    SWF_DIR = os.path.join(DEFECT_DIR, "game-files", "resources", "gpak-video", "swfs")

    if len(sys.argv) > 1:
        swfs = sys.argv[1:]
        show_all = True
    else:
        # Inspect ALL swfs for name_tag matches
        swfs = sorted(os.listdir(SWF_DIR))
        show_all = False

    for swf_name in swfs:
        if not swf_name.endswith(".swf"):
            continue
        swf_path = os.path.join(SWF_DIR, swf_name)
        if os.path.exists(swf_path):
            inspect_swf(swf_path, show_all_names=show_all)
