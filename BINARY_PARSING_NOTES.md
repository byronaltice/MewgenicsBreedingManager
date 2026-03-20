# Binary Parsing: Known Fragility & Mitigation

## Overview

The Mewgenics save file parser (`save_parser.py::Cat.__init__()`) relies on reverse-engineered binary format offsets. Where the exact format is uncertain, **fallback heuristics** are used to maximize success rate. All failures are now **logged** for debugging.

## Fragile Areas

### 1. Age Extraction (Lines 605-619)

**Problem**: Creation day is stored near the end of the blob at an unknown exact offset.

**Current approach**:
- Try multiple expected offsets from blob end: 103, 102, 104, 101, 105, 100, 106, 107, 108, 109, 110
- Accept first value where: `0 <= creation_day <= current_day` AND `0 <= age <= 100`
- If no offset succeeds, age remains `None` (not set)

**Weakness**: Could accept garbage if a valid-looking u32 appears at the wrong offset.

**Logging**: `logger.debug("Cat %s: age extraction failed", cat_key)` if all offsets fail.

**Mitigation**:
- Offset list is heuristically ordered (priority on 103, the most common case)
- Range checks (age 0-100, creation_day ≤ current_day) filter out most garbage
- Tests could validate against known saves to confirm offset accuracy

### 2. Ability Marker Detection (Lines 506-520)

**Problem**: Ability block starts with "DefaultMove" marker, but position in blob varies based on optional post-name-tag string length.

**Current approach**:
1. Scan for 4-byte length value + 4 zero bytes + ASCII string "DefaultMove" (600-byte window)
2. Validate by attempting to read 32+ identifier strings starting from marker
3. Accept first valid run (identifier regex match on each)

**Weakness**:
- If "DefaultMove" string appears elsewhere in data, parser might misidentify position
- Scanning only checks 600-byte window; if marker is outside that, fallback is used
- No validation that the run actually contains valid ability names (just checks regex)

**Logging**: `logger.debug("Cat %s: ability marker scan failed at byte %d", cat_key, i)` for each candidate that fails validation.

### 3. Ability Run Fallback Heuristic (Lines 568-598)

**Problem**: If DefaultMove marker not found, falls back to searching for any uppercase-starting ASCII string in a 500-byte window.

**Current heuristic**:
- Find first u32 length (0 < len < 64) where:
  - Next u32 is 0 (typical length-prefix pattern)
  - String starts with ASCII 65-90 (A-Z)
- If found, assume this is the ability run start
- If not found, return empty abilities list

**Weakness**:
- **Very fragile** — many legitimate binary sequences could match this pattern
- Doesn't validate that the "string" is actually a valid ability name
- Only triggers on failure to find DefaultMove, which may itself be an offset calculation error

**Logging**: `logger.debug("Cat %s: DefaultMove marker not found, using heuristic fallback", cat_key)` when fallback is triggered.

## Mitigation Strategies

### 1. Logging (✓ Implemented)
- All parsing failures are logged at DEBUG level with context (cat key, byte position)
- Enables diagnosis without changing parse behavior
- No performance impact

### 2. Testing (✓ Implemented)
- Unit tests cover BinaryReader and basic parsing
- Integration test with fixture save file would validate:
  - Age extraction against known cat ages
  - Ability marker detection against known ability lists
  - Ability run heuristic fallback behavior

### 3. Optional: Validation Data (Future)
Could add optional validation pass after Cat construction:
```python
# Pseudo-code
if cat.age is None and current_day is not None:
    logger.warning("Cat %s: age not extracted (set to None)", cat.db_key)
if not cat.abilities and not fallback_used:
    logger.warning("Cat %s: no abilities found (may indicate parsing error)", cat.db_key)
```

### 4. Optional: Reverse Engineering (Future)
If fragility proves problematic:
- Use save files with known structure to locate definitive format
- Extract offset deltas from post-name-tag anchor point
- Replace heuristics with validated fixed offsets

## Current State

✓ All failures are logged
✓ Tests provide initial validation
✓ Code handles gracefully (None for missing age, empty list for missing abilities)
✓ Users can debug with logs if issues occur

**No silent failures**: Even if age/ability extraction fails, the cat still loads with partial data and errors are logged.

## Testing Fragile Code

To validate the parser against real saves:

```bash
pytest tests/test_parser.py -v -k "test_"
# Run against fixture saves if available
# Review logs for any "fallback" or "extraction failed" messages
```

Example log output:
```
DEBUG mewgenics.parser: Cat 12345: DefaultMove marker not found, using heuristic fallback
DEBUG mewgenics.parser: Cat 12346: age extraction failed
```

These logs indicate that fallback behavior was used, but the cat still loaded successfully.
