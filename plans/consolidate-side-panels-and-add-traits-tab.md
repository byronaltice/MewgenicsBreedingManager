# Plan: Consolidate side panels and add Traits tab

## Context

The Breed Priority bottom section currently shows four equal splitter panes: **Abilities tabs** (Active/Passive/Disorder), **Mutations tabs** (Mutations/Defects), **Children panel**, and **Top Breeding Risks panel**. The two non-tabbed panels eat horizontal space and don't match the tabbed style of their neighbors.

This change collapses Children + Top Breeding Risks into a single tabbed panel (matching the existing tab style), then adds a third tab — **Traits** — that displays a unified, read-only, scrollable view of all five trait categories for the selected cat: full name and description for every Active, Passive, Disorder, Mutation, and Defect they have, grouped by category with fixed section headers. No Rating dropdown.

Result: bottom section becomes three tabbed panes of equal weight instead of four mixed ones.

## Files to modify

- `src/breed_priority/__init__.py` — primary changes (panel construction + new tab)
- `src/breed_priority/styles.py` (or wherever `TRAIT_TAB_ABILITIES_STYLE` / `TRAIT_TAB_MUTATIONS_STYLE` live) — add a third tab stylesheet if visually distinct, otherwise reuse one of the existing ones
- `src/breed_priority/constants.py` — any new color/spacing constants used by the Traits tab section headers

## Step 1 — Combine Children + Top Breeding Risk into a tabbed panel

1. Add `_make_children_risk_tab_widget()` in `src/breed_priority/__init__.py` (near [_make_mutations_tab_widget at line 1507](src/breed_priority/__init__.py:1507)).
   - Construct a `QTabWidget` styled consistently with the other two (reuse `TRAIT_TAB_ABILITIES_STYLE` or add a sibling style — match color palette of existing tabs).
   - Call existing `_make_children_panel()` ([line 1666](src/breed_priority/__init__.py:1666)) and `_make_risk_panel()` ([line 1789](src/breed_priority/__init__.py:1789)) unchanged; add their returned widgets as the first two tabs labeled `"Children"` and `"Top Risks"` (or `"Breeding Risks"` — pick whichever fits the tab width best; keep short).
2. In `_build_trait_section()` ([line 1522](src/breed_priority/__init__.py:1522)):
   - Replace the two separate `addWidget(self._make_children_panel())` and `addWidget(self._make_risk_panel())` calls with a single `addWidget(self._make_children_risk_tab_widget())`.
   - Update the docstring from "Four equal panes" to "Three equal panes: ABILITIES | MUTATIONS | CHILDREN/RISKS+TRAITS".
   - Update default pane sizes (currently `[210, 210, 220, 220]`) to three values, e.g. `[230, 230, 290]`. Note the saved `_bottom_pane_sizes` from prior sessions will have 4 entries — guard with a length check and fall back to the new default when the count mismatches (mirrors the `col_count` stamp pattern noted in CLAUDE.md).

## Step 2 — Add the Traits tab (read-only, grouped by category)

1. Add the third tab in `_make_children_risk_tab_widget()` after Children + Risks, labeled `"Traits"`.
2. Build the tab via a new `_make_all_traits_panel() -> QWidget`:
   - Outer `QWidget` with a `QVBoxLayout`.
   - Inside, a single `QScrollArea` (`setWidgetResizable(True)`) hosting a content `QWidget` with a vertical layout.
   - Render five fixed section headers (`QLabel` styled with `GROUP_LABEL_TEXT_STYLE`, same pattern as `CHILDREN` label at [line 1676](src/breed_priority/__init__.py:1676)): **Active**, **Passive**, **Disorder**, **Mutations**, **Defects** — in that order.
   - Under each header, list each trait the selected cat has as two lines: bold full display name on the first line, description below in secondary color. Reuse `self._display_name(trait)` and `self._ability_tip(trait)` / `self._mutation_tips[trait]` exactly as `_populate_trait_table()` does ([lines 2689–2705](src/breed_priority/__init__.py:2689)) so name/description formatting stays identical to the existing trait tables.
   - Each entry is its own `QLabel` (rich text with `<b>` for the name and a `<br>` + dim color for description) or a small `QWidget` row — whichever matches the project's existing rendering style for trait descriptions.
   - Hide section headers whose category is empty for the current cat (no point showing "Defects" if there are none). Show a single muted "No traits" label only if every category is empty (e.g. no cat selected).
3. Cache the references on `self`: `self._all_traits_scroll`, `self._all_traits_container`, `self._all_traits_layout` (or per-section layouts).

## Step 3 — Wire selection updates

1. Add `_refresh_all_traits_panel()` that:
   - Clears existing entries from each section's layout.
   - Reads `self._selected_cat`; if `None`, hide all sections and show the "No traits" placeholder.
   - For each of the five categories, pulls the cat's owned traits using the same source lists `_populate_trait_table()` uses (the `cat_active`, `cat_passive`, `cat_disorders`, `cat_good_mutations`, `cat_defects` derivation around [lines 1645–1662](src/breed_priority/__init__.py:1645)).
   - Builds and inserts one row per trait, then shows/hides the section header accordingly.
2. In `_on_cat_selected()` ([line 1603](src/breed_priority/__init__.py:1603)), add a call to `self._refresh_all_traits_panel()` alongside the existing `_refresh_children_panel()` / `_refresh_risk_panel()` calls.
3. If the cat data can refresh while selection stays the same (e.g. after save reload), call `_refresh_all_traits_panel()` from the same places `_refresh_trait_table_order()` is called.

## Notes / constraints

- **No Rating dropdown** in the Traits tab — it is display-only. Do not use `_make_trait_table()`, which bakes in the rating combo; build labels directly.
- Reuse name/description sources (`_display_name`, `_ability_tip`, `_mutation_tips`) verbatim. Do not invent new lookup paths — per CLAUDE.md, "If parsed data exists but lookup text is missing, use a generic fallback text."
- Section header text and any new strings should go through `_tr()` for i18n.
- Any new colors/sizes go in `src/breed_priority/constants.py`; reuse existing `GROUP_LABEL_TEXT_STYLE`, `CLR_BG_DEEP`, `CLR_TEXT_SECONDARY`, etc. where possible.
- Keep `_make_children_panel()` and `_make_risk_panel()` signatures and bodies unchanged so existing refresh logic, filters, and tooltips keep working.
- Saved-state migration: bump or guard `_bottom_pane_sizes` so old 4-entry sidecar state doesn't crash the new 3-pane splitter.

## Verification

1. `python src/mewgenics_manager.py` and load a save from `test-saves/`.
2. Bottom section shows three equal tabbed panels. The third panel has tabs: **Children**, **Top Risks**, **Traits**.
3. Select a cat with several abilities and mutations:
   - Children tab still shows the children list and its All/In Scope/Same Room filter works.
   - Top Risks tab still shows the ranked risk list.
   - Traits tab shows five labeled sections (those with content) — each entry has the same full display name and description used in the Abilities and Mutations trait tables. Vertical scrollbar appears when content exceeds the panel height.
4. Select a cat with no defects → "Defects" header is hidden; other sections still render.
5. Select different cats → all three tabs refresh in sync with the score table selection.
6. Resize the splitter, switch saves, restart the app → splitter sizes persist (or fall back gracefully if old 4-entry state existed).
