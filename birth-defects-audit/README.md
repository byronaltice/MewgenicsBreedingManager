# Birth-Defects Audit Tool

A standalone diagnostic for the missing-birth-defects bug in Mewgenics save files. Runs independently of the Breeding Manager app.

If you build tools that read Mewgenics saves, read [MISSING_BIRTH_DEFECTS_REPORT.md](./MISSING_BIRTH_DEFECTS_REPORT.md) first. The short version: some birth defects are not stored in the cat's data on disk; they are computed at runtime from the cat's `headShape` and a SWF animation. Tools that only scan mutation tables miss them.

## How to check if my save file has any weird cats?

Copy this directory anywhere, install one Python dependency, and run.

## Why do I need this?

- You are running a save file parser, and you want to parse cat's birth defects. Most of the time, a straigthforward save file reading works, but there are certain birth defects that won't show up.
- You want to see if your current save file parser catches the missing defects (it probably won't), and you need to find cats in your save file that have this issue to verify.

## What if my save file parser already catches defects?

It probably catches most of them, but not all. This took me two full weeks of searching through decompiled code to understand how the game calculates some uncommon birth defects. If you haven't been doing the same thing, then you probably don't know about it.

## What's in this directory?

| File | Purpose |
|---|---|
| `MISSING_BIRTH_DEFECTS_REPORT.md` | The full bug + fix writeup. Python and JavaScript fix examples included. |
| `audit_missing_birth_defects.py` | Standalone diagnostic. Lists cats whose defects a naive parser would miss, and their missing defects (not the normal defects). |
| `swf_anchor_walker.py` | The SWF parser the audit uses. Reusable; a complete reference implementation. |
| `example_save.sav` | A reference save the report's example numbers come from (947 cats, 15 affected). |

## Requirements

- Python 3.10 or newer
- The `lz4` package: `pip install lz4`
- A copy of `resources.gpak` from your Mewgenics install. The audit needs it to read the `CatHeadPlacements` SWF clip.

The gpak typically lives at:

- Windows: `C:\Program Files (x86)\Steam\steamapps\common\Mewgenics\resources.gpak`
- WSL: `/mnt/c/Program Files (x86)/Steam/steamapps/common/Mewgenics/resources.gpak`

## Finding Missing Defects

Default — uses the bundled example save:

```
python3 audit_missing_birth_defects.py --gpak /path/to/resources.gpak
```

Against your own save:

```
python3 audit_missing_birth_defects.py /path/to/your.sav --gpak /path/to/resources.gpak
```

Output looks like this (15 cats from the bundled example save):

```
Save        : .../example_save.sav
GPAK        : .../resources.gpak
SWF frames  : 1505
Cats parsed : 947

Cats affected by SWF-anchor-absence defects: 15

db_key  name                      headShape  predicted defects
------------------------------------------------------------------------------------------------
   296  Fuzz                            309  Right Ear Birth Defect, Right Eye Birth Defect, Right Eyebrow Birth Defect
   ...
   853  Whommie                         304  Right Eye Birth Defect, Right Eyebrow Birth Defect
   887  Bud                             319  Left Ear Birth Defect, Right Ear Birth Defect
   ...
```

The "predicted defects" column lists ONLY the defects that are found by this extra parsing step. It DOES NOT list any defects that would normally be parsed without the fix.

## How it works (one paragraph)

The audit opens the SQLite save, decompresses each cat's LZ4 blob, walks the variable-length blob header far enough to extract the cat's name and `headShape`, then independently extracts the `CatHeadPlacements` SWF clip from the gpak and walks its tag stream once to build a per-frame anchor presence list. For each cat, it checks `per_frame_anchors[headShape - 1]` (note the off-by-one — the game runtime seeks to `headShape - 1`, not `headShape`) and reports cats where any of the visible-slot anchor names (`leye`, `reye`, `lear`, `rear`, `mouth`) are absent.

For the underlying mechanism including why this happens and how to write a save parser that handles it see [MISSING_BIRTH_DEFECTS_REPORT.md](./MISSING_BIRTH_DEFECTS_REPORT.md).
