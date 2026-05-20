# Symbol Extraction Report

## Library Used

**pyswf 1.5.4** was installed (`pip install pyswf`) but is Python 2-only and cannot be imported under Python 3.14 due to bare relative imports.

**Resolution:** A pure-Python SWF parser and Skia-based renderer was written from scratch:

- `defect-investigation/scripts/extract-symbols/swf_parser.py` — SWF header decompression, tag stream reader, DefineBitsLossless/JPEG bitmap extractor, SymbolClass/ExportAssets name extractor
- `defect-investigation/scripts/extract-symbols/swf_shape_renderer.py` — DefineShape 1–4 binary parser (bit-stream, RECT, MATRIX, fill/line styles, edge/non-edge records), Skia-based polygon renderer
- `defect-investigation/scripts/extract-symbols/extract_sprites.py` — DefineSprite recursive traversal, multi-shape compositing renderer
- `defect-investigation/scripts/extract-symbols/extract_final_icons.py` — targeted extraction of the 18 FontIcon sprites

Dependencies used: `skia-python` (rendering), `Pillow` (PNG I/O and crop), `zlib` (SWF decompression, baked into Python stdlib).

## Where Each Icon Lives

All 18 icons are in **`ui.swf`** as `FontIcon_<name_tag>` sprites. They are white or black vector glyphs (DefineShape records inside DefineSprite wrappers) — the game is using a glyph-font system where each icon is a named sprite rendered as a monochrome shape over a dynamically colored background.

| name_tag | SWF | Symbol Name | Char ID | Dimensions |
|---|---|---|---|---|
| str | ui.swf | FontIcon_str | 2704 | 313 × 328 px |
| dex | ui.swf | FontIcon_dex | 2713 | 318 × 258 px |
| con | ui.swf | FontIcon_con | 2716 | 322 × 258 px |
| int | ui.swf | FontIcon_int | 2710 | 406 × 440 px |
| spd | ui.swf | FontIcon_spd | 2707 | 429 × 264 px |
| cha | ui.swf | FontIcon_cha | 2719 | 383 × 245 px |
| lck | ui.swf | FontIcon_lck | 3897 | 319 × 336 px |
| stimulation | ui.swf | FontIcon_stimulation | 2685 | 698 × 620 px |
| comfort | ui.swf | FontIcon_comfort | 2687 | 631 × 632 px |
| appeal | ui.swf | FontIcon_appeal | 2689 | 589 × 641 px |
| health | ui.swf | FontIcon_health | 2665 | 437 × 647 px |
| evolution | ui.swf | FontIcon_evolution | 2663 | 636 × 635 px |
| star2 | ui.swf | FontIcon_star2 | 2659 | 687 × 653 px |
| circle | ui.swf | FontIcon_circle | 2681 | 561 × 561 px |
| triangle | ui.swf | FontIcon_triangle | 2677 | 589 × 511 px |
| sword | ui.swf | FontIcon_sword | 2673 | 515 × 515 px |
| shield2 | ui.swf | FontIcon_shield2 | 2661 | 556 × 575 px |
| poop | ui.swf | FontIcon_poop | 2671 | 596 × 561 px |

Dimensions are post-crop (transparent border removed), rendered at scale 10 px/SWF-pixel (500 px per inch equivalent). The originals are vector and can be re-rendered at any size.

## Icon Colors

- **Stat icons** (str/dex/con/int/spd/cha/lck): black fill on transparent background
- **Room-stat icons** (stimulation/comfort/appeal/health/evolution): white fill on transparent background
- **Shape/object icons** (star2/circle/triangle/sword/shield2/poop): white fill on transparent background

The game composites these over colored chip backgrounds at runtime.

## Visual Verification

All 18 icons were visually confirmed:
- **str** — bicep/muscle arm (black)
- **dex** — bow and arrow through a circle (black)
- **con** — heart (black)
- **int** — lightbulb (black)
- **spd** — boot (black)
- **cha** — lips/mouth (black)
- **lck** — four-leaf clover (black)
- **stimulation** — yarn ball (white)
- **comfort** — sleeping cat with Z (white)
- **appeal** — house silhouette (white)
- **health** — snake-and-staff caduceus (white)
- **evolution** — DNA double helix (white)
- **star2** — five-pointed star (white)
- **circle** — circle (white)
- **triangle** — triangle (white)
- **sword** — sword (white)
- **shield2** — shield with pointed bottom (white)
- **poop** — poop emoji shape (white)

## Tags Not Found

None. All 18 requested tags were found and extracted.

Note: The task description mentions 19 icons but the table contains 18 rows (str/dex/con/int/spd/cha/lck = 7, stimulation/comfort/appeal/health/evolution = 5, star2/circle/triangle/sword/shield2/poop = 6; total = 18). All 18 are present.

## Staging Directory

Final assets: `defect-investigation/audit/direction/symbol-final/`

Each file is named `<name_tag>.png` (e.g. `str.png`, `appeal.png`, `star2.png`).

Preview images with backgrounds (for visibility in file viewers):
`defect-investigation/audit/direction/symbol-preview/`

Intermediate candidates (all extracted sprites from ui.swf):
`defect-investigation/audit/direction/symbol-candidates/ui/`

## Scripts

All scripts are in `defect-investigation/scripts/extract-symbols/`:

| Script | Purpose |
|---|---|
| `swf_parser.py` | Low-level SWF binary parser (bitmaps, symbol names) |
| `swf_shape_renderer.py` | DefineShape* parser + Skia PNG renderer |
| `extract_sprites.py` | DefineSprite traversal + multi-shape compositor |
| `extract_final_icons.py` | Targeted FontIcon extraction + staging |
| `explore_swf.py` | SWF explorer (initial investigation) |
| `inspect_swf_tags.py` | Tag-type survey across all SWFs |
| `extract_all.py` | Bulk bitmap extractor (initial investigation) |
