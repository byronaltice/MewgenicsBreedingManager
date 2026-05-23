# Plan: Compare Profiles dialog — polish & fixes

## Context

The Profile Compare ("…") dialog was shipped in `src/breed_priority/profile_compare/`. In use, it has several rendering, layout, and behavior problems the operator wants fixed in one pass:

1. **Open flicker** — dialog flashes bright white full-screen, then shrinks to a tiny window in the top-left after content loads.
2. **Sizing** — should not be full-screen. Either match the main window's current size, or (preferred) render as a full-window overlay inside the main window itself (cannot return to main window without dismissing).
3. **Left column readability** — row label font is too small.
4. **No alternating row background** — rows blur together visually.
5. **Weight spin layout** — the up/down arrows have dead space between them and the number. The main weights popup hugs the number; this should match.
6. **Column widths** — every column is fixed-width (`COL_SLOT_WIDTH`), wasting space. Should size-to-content and left-align.
7. **Hidden profiles leave gaps** — toggling a slot's include-checkbox off hides its widgets but leaves the column slot empty. Visible columns should pack left.
8. **Empty slots show editor values** — slots 2/3/4 (no saved profile) show populated editor widgets instead of an empty placeholder. The empty-state path is dead code: `_build_grid_content` passes `present_slots = set(range(1, NUM_PROFILES + 1))`, so the `if n not in present_slots: _empty_label()` branch in `rows.py` never runs.
9. **"Show only differences" hides everything** — diff filter hides every data row because `_get_editor_value` always returns the `_EMPTY` sentinel (it's a stub).
10. **"Show only differences" hard-hides matching rows** — operator wants matching rows visible but greyed/dimmed, not hidden.

## Files to modify

- `src/breed_priority/profile_compare/dialog.py` — sizing/overlay, present_slots logic, diff comparison, slot-hide column packing, root background, loading state.
- `src/breed_priority/profile_compare/rows.py` — label font size, row striping, column auto-sizing, empty-slot rendering integration.
- `src/breed_priority/profile_compare/constants.py` — new style/size constants.
- `src/breed_priority/__init__.py` — `_open_profile_compare` may need to pass the main-window reference for overlay sizing, or just pass main-window geometry. (Only touch this method.)
- `src/breed_priority/widgets.py` — `_WeightSpin` arrow layout. Likely a `QStyle` / `QAbstractSpinBox` setting (`setButtonSymbols`, internal margins) — investigate before changing; if the main app's weights popup is already correct, copy its setup verbatim. The reference for the desired hug-the-number look is at `src/breed_priority/__init__.py:1300-1306` and how `_WeightSpin` is used in the weights popup grid. **Important:** do not break the weights popup if `_WeightSpin` is shared between both. If the fix needs to be local to the compare dialog only, subclass or wrap rather than mutate the shared class. Confirm by grepping usages of `_WeightSpin` and `_IntParamSpin`.

## Fix-by-fix details

### 1 & 2 & 3 (open flicker + sizing): replace `showMaximized()` with a sized geometry

In `ProfileCompareDialog.__init__`:

- **Remove** `self.showMaximized()`.
- Set the stylesheet on `self` **before** building UI so the background is dark from frame one (currently set at line 100 — keep this, just ensure it runs before any `.show()`).
- Replace with geometry derived from the parent's main-window rect:
  ```python
  mw = parent.window() if parent is not None else None
  if mw is not None:
      self.setGeometry(mw.geometry())
  else:
      self.resize(1400, 900)
  ```
- Keep `setModal(True)`. Caller uses `exec()` which will block parent input as long as modal.
- Do **not** call `showMaximized()`; let `exec()` from the caller handle the show. If a show is needed before geometry takes effect, call `self.setGeometry(...)` before `exec()` returns control — the caller already does `dlg = ProfileCompareDialog(...); dlg.exec()`. Setting geometry in `__init__` is sufficient.
- Set `Qt.WA_StyledBackground, True` on the dialog so the QSS background paints on the dialog itself (this is the white-flash fix — Qt's default `QDialog` doesn't honor the stylesheet background unless this attribute is set, which is also why it briefly shows the OS window background).

### Loading indicator (optional, only if construction is slow)

Construction of all editors for 5 slots × every weight × every trait can take a noticeable beat. If after the above fix the dialog still shows visible empty time:

- Show a centered "Loading…" `QLabel` immediately, run `QApplication.processEvents()`, then call `self._build_ui()`. Hide the loading label after build.

Treat this as best-effort — if it's snappy enough after fixing the white-flash, skip it and note in the report.

### 4 (left column font): bump font size

In `rows.py::_label_widget`, change `font-size:10px;` to `font-size:11px;` (or 12px if it still feels small — pick one based on visual check). Add a new constant `LABEL_FONT_SIZE_PX = 11` in `constants.py` and reference it.

### 5 (alternating row backgrounds)

In `RowTracker` or in each `add_*_row` helper, track the row parity. Wrap the label and each editor in a row-background container, or apply a per-widget stylesheet background.

Cleanest approach: add a new helper `_apply_row_stripe(row_widgets: list[QWidget], parity: int)` and call it after every `tracker.data_rows.append(...)`. Define two background hex constants in `constants.py`:

```python
ROW_BG_EVEN = "#0c1424"  # match CLR_SURFACE_APP_MAIN or a near-shade
ROW_BG_ODD  = "#101a2e"  # slightly lighter
```

(Confirm exact hex by sampling existing theme values from `src/breed_priority/theme.py`; ideally introduce them there to keep theme centralization.)

Stripe must survive visibility changes (Q4 below) — so the background must be on the widget itself, not on the grid cell.

### 6 (column auto-sizing & left-align)

- In `rows.py`, **remove** `setFixedWidth(COL_SLOT_WIDTH)` on every editor and on `_label_widget` (keep a min width on labels only).
- In `dialog.py::_build_ui`, remove the `setColumnMinimumWidth` calls for columns 1..5. Keep one for col 0 (labels).
- Set every editor cell alignment to `Qt.AlignLeft | Qt.AlignVCenter` via `grid.addWidget(w, r, n, Qt.AlignLeft | Qt.AlignVCenter)`.
- After the grid is populated, columns will size to their content. For consistency across rows in the same column, use `grid.setColumnStretch(col, 0)` on data columns and add a `grid.setColumnStretch(NUM_PROFILES + 1, 1)` on a trailing spacer column to consume leftover space (so columns hug left instead of evenly distributing).

### 7 (hidden profiles pack left)

A `QGridLayout` cannot reflow — hiding column N leaves a gap. Two viable approaches:

- **Preferred:** keep `QGridLayout` but **re-map slot → grid column** on every include toggle. Maintain `self._slot_to_col: dict[int, int]`. When include state changes, recompute the mapping (sorted by slot among included slots), iterate every row's `editors` dict, and `grid.removeWidget(w)` + `grid.addWidget(w, r, new_col)`. Hidden editors stay parented (`setVisible(False)`) and are not added to the grid; their column simply isn't used.
- **Alternative:** rebuild the grid from scratch on every include toggle. Simpler but worse UX (focus loss, slight flicker).

Go with the preferred approach. Implementation note: also re-layout the section-header `setColumnSpan` (currently `1, num_cols + 1` spanning all columns) so it spans `1 + visible_count`. Track header rows with their span via `RowTracker.header_rows` (already tracked).

### 8 (empty-slot rendering)

Root cause: `_build_grid_content` passes `present_slots = set(range(1, NUM_PROFILES + 1))`. Fix:

```python
present_slots = {n for n in range(1, NUM_PROFILES + 1) if n not in self._was_empty}
```

This makes every row helper render `_empty_label()` for empty slots — already implemented in `rows.py`, just dead.

For empty slots, the include checkbox should still work but the slot column shows the placeholder. The plan section 7 (column packing) still applies — empty slots hidden via include toggle pack left the same way.

**Edit-empty-slot UX:** the operator's original spec said empty slots should be editable so a new profile can be created from the compare view. Defer that — current scope reverts to "empty slots show placeholder; cannot edit from compare view." If the operator wants editing back, add a per-empty-slot "+ Add profile" button as a follow-up. Call this out in the agent's final report.

### 9 & 10 (diff filter: use staged dict; grey instead of hide)

Rewrite `_refresh_diff_visibility` and remove `_get_editor_value` (the stub). The staged dict is the source of truth — every change handler already writes to it.

Each data row needs to know its key path into the staged blob so we can read it without touching the widget. Extend `RowTracker.data_rows` from `list[tuple[QLabel, dict[int, QWidget]]]` to `list[RowDescriptor]`:

```python
@dataclass
class RowDescriptor:
    label: QLabel
    editors: dict[int, QWidget]
    value_getter: Callable[[dict, int], object]  # (staged_blob, slot) -> value
```

For each row type, define a getter:

- Name → `lambda blob, _slot: blob.get("name", "")`
- Weight key K → `lambda blob, _slot, k=K: blob.get("weights", {}).get(k)`
- Complex weight ID X → `lambda blob, _slot, x=X: x in (blob.get("complex_weights_enabled_ids") or [])`
- Trait T → `lambda blob, _slot, t=T: blob.get("ma_ratings", {}).get(t, 0)` (treat missing as 0)
- For empty slots (in `self._was_empty`): return `_EMPTY` sentinel.

Each `add_*` helper now appends a `RowDescriptor` to the tracker.

In `_refresh_diff_visibility`:

```python
included = [n for n in range(1, NUM_PROFILES + 1) if self._include_checks[n].isChecked()]
diff_on = self._diff_chk.isChecked()

for desc in self._tracker.data_rows:
    if diff_on:
        values = [desc.value_getter(self._staged[n], n) if n not in self._was_empty else _EMPTY
                  for n in included]
        same = len({_hashable(v) for v in values}) <= 1
    else:
        same = False  # always treat as differing → no greying

    # Always show row; grey out when same and diff filter is on
    desc.label.setEnabled(not same)
    for n, w in desc.editors.items():
        slot_visible = self._include_checks[n].isChecked()
        w.setVisible(slot_visible)
        w.setEnabled(not same)
```

`setEnabled(False)` automatically dims the widget with Qt's disabled palette. If the visual dimming isn't strong enough, also apply a stylesheet `opacity` via a property selector or a wrapper widget — but try `setEnabled` first.

When diff is **off**, re-enable everything.

### Misc cleanups in the same pass

- The `_DIFF_CHK_STYLE` has font-size 10px while `_INCLUDE_CHK_STYLE` is 11px — make them match (11px).
- The empty-slot label in `_empty_label()` uses `setFixedWidth(COL_SLOT_WIDTH)` — drop the fixed width per Q6 changes.
- Verify the dialog still closes cleanly (Esc, X) and Apply still returns `result_profiles` for the loaded-slot refresh path.

## Verification

No tests in repo. After implementation:

1. `python -m py_compile` all changed files.
2. Run `python src/mewgenics_manager.py`, load a save from `test-saves/`.
3. Click "…" — confirm:
   - Dialog opens at main-window size, no white flash, dark background from frame one.
   - Left-column labels are readable (slightly larger than before).
   - Rows alternate background shades.
   - Weight spinners hug the number (no dead space between arrows and value).
   - Columns are compact and left-aligned; empty trailing space on the right.
4. With only slot 1 saved, confirm slots 2–5 show `— empty —` placeholders (not editor widgets).
5. Save into slots 2 and 3 with different weights/ratings.
6. Toggle slot 2's include off → confirm slot 2 column disappears and slots 3/4/5 pack left to fill the gap.
7. Toggle slot 2 back on → returns to its position.
8. Check "Show only differences" → confirm differing rows look normal, matching rows appear greyed-out (still visible). With only one slot included, all rows should be grey (single value = no differences).
9. Apply edits, confirm sidecar persists per the original spec.

## Out of scope

- Editing empty profile slots from the compare view (deferred — call out in report).
- Localization (`_tr`) wrapping of new constants (none introduced).
- Changes to the main weights popup.
