# Plan: Compare Profiles dialog — polish pass 2

## Context

Four follow-up fixes for `src/breed_priority/profile_compare/`:

1. **Hide blank profiles entirely** — no toggle, no column, no checkbox in the toolbar.
2. **Group headers (Name, Weights, etc.) need to stand out** — currently smaller and darker than the rows below them.
3. **Remove "Flat Trait Scoring" row** from the Weights group.
4. **Trait names lack emoji formatting** — main window renders mutation names like `Body Mutation +2💪, -1💡` (via `StatTextFormatter.emojify`), but the compare dialog shows raw `+2 STR, -1 INT` style text. Make compare match the main window.

## Files to modify

- `src/breed_priority/profile_compare/dialog.py` — drop empty slots from toolbar + grid construction.
- `src/breed_priority/profile_compare/rows.py` — section-header styling, drop `trait_flat_scoring` row, emojify trait labels.
- `src/breed_priority/profile_compare/constants.py` — new style constants.
- `src/breed_priority/__init__.py` (`_open_profile_compare` only) — pass a `display_name` callable so `rows.py` can resolve trait → human display name without importing from the main view.

## Fix-by-fix

### 1. Hide blank profiles entirely

Currently `dialog.py` tracks `self._was_empty` and still creates editors/include-checkboxes for empty slots. Replace with a single set of *visible slots*:

```python
self._visible_slots = sorted(n for n in range(1, NUM_PROFILES + 1) if n in profiles)
# self._staged still seeded for visible slots only; drop _empty_blob path entirely.
self._staged = {n: copy.deepcopy(profiles[n]) for n in self._visible_slots}
self._was_empty = set()  # remove entirely; no callers needed after edits below
```

Toolbar (`_build_toolbar`): iterate `self._visible_slots` instead of `range(1, NUM_PROFILES + 1)` when building include-checkboxes. The "Slots:" label can be hidden if `len(self._visible_slots) <= 1` (no point including/excluding).

Grid (`_build_grid_content`): pass `present_slots = set(self._visible_slots)`. The `_empty_label()` branch in `rows.py` becomes unreachable — keep it as a defensive fallback or delete it; recommend deleting (`_empty_label` and `EMPTY_SLOT_PLACEHOLDER`).

Slot-to-column packing logic (the include-toggle remap from polish pass 1) keeps working — `self._visible_slots` is the universe it operates over.

If `len(self._visible_slots) == 0` (no saved profiles at all): show a single centered "No saved profiles to compare." label and an OK button; skip building the grid. `_open_profile_compare` in `__init__.py` should also early-return with an info message before opening the dialog — check that first.

### 2. Group header styling

Currently `_section_header()` in `rows.py:38-46`:

```python
f"color:{CLR_TEXT_LABEL_GROUP}; font-size:10px; font-weight:bold;"
f" letter-spacing:1px; border-bottom:1px solid {CLR_SURFACE_SEPARATOR};"
" padding:4px 0 2px 0;"
```

Row labels are 11px (per `LABEL_FONT_SIZE_PX` from pass 1). Headers should be visually dominant. Change to something like:

```python
f"color:#cce0ff; font-size:14px; font-weight:bold;"
f" letter-spacing:2px; border-bottom:1px solid #2a4a8a;"
" padding:10px 0 4px 0; margin-top:6px;"
```

Add the values to `constants.py`:
- `SECTION_HEADER_FONT_SIZE_PX = 14`
- `SECTION_HEADER_COLOR = "#cce0ff"` (or sample a brighter shade from `theme.py` — prefer reusing an existing constant like a brighter variant; only add a new theme constant if nothing fits)
- `SECTION_HEADER_BORDER_COLOR = "#2a4a8a"`

Confirm visual after change — the goal is "obviously a group header at a glance," even when scrolling. If borderless looks cleaner, drop the border-bottom in favor of a slightly different background row.

### 3. Remove "Flat Trait Scoring" row

In `rows.py::add_weight_rows`, delete the entire "Flat trait scoring checkbox row" block (currently appended after the WEIGHT_UI_ROWS loop — search for `"Flat trait scoring"` and remove the row construction + the `tracker.data_rows.append((lbl, editors))` for it).

Important: do **not** strip the `trait_flat_scoring` key from the staged dict on Apply — leave whatever value was already in each profile untouched so the operator's setting from the main weights popup is preserved. Just stop exposing it as a compare-dialog row.

### 4. Emoji-formatted trait names

The main window resolves a trait key (e.g. `"BodyMut_2STR_-1INT"` or similar) into a display name via `self._display_name(trait)` and then emojifies with `StatTextFormatter.emojify(...)`. See `src/breed_priority/__init__.py:2849-2852` for the exact two-line pattern.

Currently `rows.py::add_trait_rows` uses the raw trait key as the row label:

```python
lbl = _label_widget(trait)
```

**Fix:**

1. In `dialog.py`, accept a new constructor parameter `display_name_fn: Callable[[str], str]` (defaulting to `lambda t: t`). The caller in `__init__.py::_open_profile_compare` passes `self._display_name`.
2. In `dialog.py::_build_grid_content`, build the emojified label up front:
   ```python
   from ..stat_text_formatter import StatTextFormatter
   def _trait_label(trait: str) -> str:
       return StatTextFormatter.emojify(self._display_name_fn(trait))
   ```
   Pass `_trait_label` into `add_trait_rows` as a new `label_fn` parameter.
3. `rows.py::add_trait_rows` uses `label_fn(trait)` when building `_label_widget`.

Width: emojified labels can be slightly wider than raw trait keys. Bump `COL_LABEL_WIDTH` in `constants.py` modestly (e.g. 240 → 280) and verify the layout still feels tight. The labels are min-width, not fixed, so they'll expand naturally if more is needed — but the column has a fixed minimum to keep all rows aligned, so update that minimum.

**Defense:** if `display_name_fn(trait)` raises or returns empty, fall back to the raw `trait` string. Wrap in try/except in `_trait_label` to keep one bad lookup from breaking the whole dialog.

## Verification

1. `python -m py_compile` on changed files.
2. Run `python src/mewgenics_manager.py`, load a save with only some slots saved (e.g. 1 and 5).
3. Confirm:
   - Only slots 1 and 5 appear in the toolbar — no checkbox for 2/3/4. Grid columns: label + 2 data columns, packed left.
   - Section headers (`Name`, `Weights`, `Complex Weights`, `Active Abilities`, ...) are visually larger / brighter than the row labels beneath them.
   - "Flat trait scoring" is gone.
   - Trait rows under "Active Abilities" / "Passive Abilities" / "Disorders" / "Good Mutations" / "Defects" show emoji-formatted names matching the main window's mutations/abilities panel (e.g. `+2💪, -1💡` instead of `+2 STR, -1 INT`).
4. Toggle a slot include checkbox off → other visible slot still packs left (regression check from pass 1).
5. Apply edits → confirm sidecar still writes correctly and `trait_flat_scoring` values are untouched in stored blobs.
6. Edge case: open with **no** saved profiles → confirm graceful "nothing to compare" handling (info message at the `_open_profile_compare` call site is enough).
