# Obsolete Findings

Findings that were later proven wrong or superseded. Read before treating older findings as valid.

---

## Direction 42 Misidentification — `FUN_1401d2ff0` as per-cat save loader

**Original claim (Direction 42):** `FUN_1401d2ff0` was identified as the per-cat save loader and a source of load-time defect application.

**Correction (Direction 43):** `FUN_1401d2ff0` is `GlobalProgressionData::ComputeSaveFilePercentage`. It applies progression-milestone mutations gated on `save_file_percent` vs `save_file_next_cat_mutation`. In the investigation save (`save_file_percent=80`, `save_file_next_cat_mutation=90`) this path is entirely gated off and performs zero `FUN_1400ca4a0` calls. Even when active, the candidate table `_DAT_141130700` only covers body/head/tail/rear legs/front legs — it cannot produce eye/eyebrow/ear defects.

---

## `FUN_140734760` as placement-only

**Original claim (Direction 45):** `FUN_140734760` was identified as a bone/transform placement function only.

**Correction (Direction 47):** `FUN_140734760` also clears facial/attached `CatPart+0x18` present flags and selectively sets them back to 1 based on anchor names in the `CatHeadPlacements` GON entry for the current head ID. It is the first confirmed missing-flag setter. See `DEFECT_INVESTIGATION.md` Direction 47.
