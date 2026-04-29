# Missing Birth Defects in Mewgenics Save Files — Detection & Fix

A report for tool authors, modders, and anyone reading Mewgenics save data outside the game itself.

## TL;DR

Some cats carry birth defects that **never appear as data on disk**. The defect is computed at runtime from one byte (`headShape`) and a SWF animation file. If your tool only reads the cat's mutation table, you will silently miss these defects on roughly 1.6% of cats in a typical save (15 out of 947 in the reference save tested).

The fix is small and self-contained: replicate the same SWF-frame-walk the game performs, check which "anchor" names are present at frame `headShape - 1` of the `CatHeadPlacements` clip, and synthesize defect entries when expected anchors are absent.

---

## What the bug looks like

A cat in your tool shows fewer defects than the same cat shows in-game.

Concrete examples from the reference save:

| Cat | `headShape` | Defects in-game | Defects from naive parsing |
|---|---|---|---|
| Whommie | 304 | Eye Birth Defect (Blind), Eyebrow Birth Defect (-2 CHA), Fur Birth Defect | only Fur Birth Defect |
| Bud | 319 | Leg Birth Defect, Ear Birth Defect (-2 DEX) | only Leg Birth Defect |
| Murisha | 323 | Ear Birth Defect | (none) |

Naive parsing means: scan the cat's per-slot mutation IDs, flag entries whose ID is `0xFFFFFFFE` (the explicit defect placeholder) or whose ID lives in a GON block tagged `birth_defect`. That covers roughly 17 cats per save — but misses the SWF-anchor-absence class entirely.

---

## How to fix it

You need three things at runtime:

1. The cat's `headShape` value (a 32-bit integer in the cat's mutation/identity table — index 8 in the table layout used by this project).
2. A precomputed list of which "anchor" names are present at each frame of the `CatHeadPlacements` SWF clip (character ID `11007`, found in `swfs/catparts.swf` inside `resources.gpak`).
3. A mapping from anchor names to the cat's part slots, plus an "eye → eyebrow" propagation rule.

Then per cat:
- Look up `per_frame_anchors[headShape - 1]`. (Note the off-by-one — the game seeks to `headShape - 1`, not `headShape`.)
- Compute missing = `ALL_ANCHORS - present`.
- For each missing anchor, append a defect entry for the corresponding part slot.
- If `leye` or `reye` is missing, also append a defect for the matching eyebrow slot.

The 8 anchor names the game checks: `leye, reye, lear, rear, mouth, ahead, aneck, aface`. Only the first five map to visible defect slots; `ahead`, `aneck`, `aface` exist in the SWF but have no part-slot mapping.

### Python example

```python
ALL_ANCHORS = frozenset({
    "leye", "reye", "lear", "rear", "mouth", "ahead", "aneck", "aface"
})

# Anchor name -> slot the defect should appear in.
# 'ahead', 'aneck', 'aface' intentionally omitted (no visible slot).
ANCHOR_TO_SLOT = {
    "leye":  "eye_L",
    "reye":  "eye_R",
    "lear":  "ear_L",
    "rear":  "ear_R",
    "mouth": "mouth",
}

# Eye -> eyebrow propagation: when an eye anchor is absent, the matching
# eyebrow slot is also defective. This is the game's behavior, baked into
# the runtime function that updates the part-present flags.
EYE_TO_EYEBROW_SLOT = {
    "leye": "eyebrow_L",
    "reye": "eyebrow_R",
}

DEFECT_ID = 0xFFFFFFFE


def synthesize_swf_defects(cat_visual_entries, head_shape, per_frame_anchors):
    """Append birth-defect entries for SWF-anchor-absence defects.

    cat_visual_entries: list of dicts your tool already builds from the cat's
        mutation table. Each entry has at least a 'slot_key' string and an
        'is_defect' bool. Mutated in place.
    head_shape: int from the cat's data (table[8] in this project's layout).
    per_frame_anchors: list[frozenset[str]], indexed by 0-based frame number.
        Element k is the set of anchor names present at frame k of the
        CatHeadPlacements SWF clip under cumulative display-list semantics.
    """
    if not per_frame_anchors:
        return  # no SWF data loaded — skip rather than false-flag every cat

    target_frame = head_shape - 1
    if target_frame < 0 or target_frame >= len(per_frame_anchors):
        return

    present = per_frame_anchors[target_frame]
    missing = ALL_ANCHORS - present

    already_flagged = {
        e["slot_key"] for e in cat_visual_entries if e.get("is_defect")
    }

    def add_defect(slot_key):
        if slot_key in already_flagged:
            return
        cat_visual_entries.append({
            "slot_key": slot_key,
            "mutation_id": DEFECT_ID,
            "is_defect": True,
            # Add display-name, stat-text, etc. as your tool requires.
        })
        already_flagged.add(slot_key)

    for anchor in missing:
        slot = ANCHOR_TO_SLOT.get(anchor)
        if slot:
            add_defect(slot)
        eyebrow_slot = EYE_TO_EYEBROW_SLOT.get(anchor)
        if eyebrow_slot:
            add_defect(eyebrow_slot)
```

The hard part is producing `per_frame_anchors`. That requires walking the SWF's `DefineSprite` tag stream for character ID `11007` and, frame-by-frame, applying `PlaceObject2/3` (tag types 26, 70) and `RemoveObject2` (tag type 28) to a depth-keyed display list, snapshotting the names of children that fall in `ALL_ANCHORS` after each `ShowFrame` (tag type 1).

Critical details:
- Use **inclusive** frame semantics: a tag labeled `frame=N` is committed when seeking to frame N or later. The game's runtime is spec-compliant on this.
- **Do NOT skip RemoveObject2.** The defect-producing head shapes use it specifically — the missing-anchor pattern is "remove at frame N-1, re-place at frame N", so seeking to N-1 sees the anchor as absent while seeking to N sees it as present.
- Build snapshots in O(N), not O(N²) — apply each tag once as you advance the frame counter, snapshot after every `ShowFrame`. Naïvely re-walking from frame 0 for every snapshot turns a 40 ms parse into a 32-second one.

A complete reference implementation in Python is in this project at `src/swf_anchor_walker.py` (~470 lines including SWF tag parsing).

### JavaScript example

The same logic in JavaScript / TypeScript:

```javascript
const ALL_ANCHORS = new Set([
    "leye", "reye", "lear", "rear", "mouth", "ahead", "aneck", "aface"
]);

const ANCHOR_TO_SLOT = {
    leye:  "eye_L",
    reye:  "eye_R",
    lear:  "ear_L",
    rear:  "ear_R",
    mouth: "mouth",
};

const EYE_TO_EYEBROW_SLOT = {
    leye: "eyebrow_L",
    reye: "eyebrow_R",
};

const DEFECT_ID = 0xFFFFFFFE;


/**
 * Append birth-defect entries for SWF-anchor-absence defects.
 *
 * @param {Array<Object>} catVisualEntries  - mutated in place; each entry has
 *   at least a `slotKey` string and an `isDefect` bool.
 * @param {number} headShape                - from cat data (table[8]).
 * @param {Array<Set<string>>} perFrameAnchors - indexed by 0-based frame number;
 *   element k is the set of anchor names present at frame k under cumulative
 *   display-list semantics.
 */
function synthesizeSwfDefects(catVisualEntries, headShape, perFrameAnchors) {
    if (!perFrameAnchors || perFrameAnchors.length === 0) {
        return;  // no SWF data loaded — skip rather than false-flag every cat
    }

    const targetFrame = headShape - 1;
    if (targetFrame < 0 || targetFrame >= perFrameAnchors.length) {
        return;
    }

    const present = perFrameAnchors[targetFrame];
    const missing = new Set();
    for (const a of ALL_ANCHORS) {
        if (!present.has(a)) missing.add(a);
    }

    const alreadyFlagged = new Set(
        catVisualEntries
            .filter(e => e.isDefect)
            .map(e => e.slotKey)
    );

    const addDefect = (slotKey) => {
        if (alreadyFlagged.has(slotKey)) return;
        catVisualEntries.push({
            slotKey,
            mutationId: DEFECT_ID,
            isDefect: true,
            // Add displayName, statText, etc. as your tool requires.
        });
        alreadyFlagged.add(slotKey);
    };

    for (const anchor of missing) {
        const slot = ANCHOR_TO_SLOT[anchor];
        if (slot) addDefect(slot);
        const eyebrowSlot = EYE_TO_EYEBROW_SLOT[anchor];
        if (eyebrowSlot) addDefect(eyebrowSlot);
    }
}
```

For the SWF parsing portion in JavaScript, any standard SWF library that exposes `DefineSprite` bodies as a tag stream will do; if you need raw byte parsing, the SWF file format spec is publicly available from Adobe and the relevant tag types are 1 (`ShowFrame`), 26 (`PlaceObject2`), 28 (`RemoveObject2`), and 70 (`PlaceObject3`). Tag types 5 and 6 do not appear in `CatHeadPlacements`, but a complete walker should at least skip them safely.

---

## Why this happens — the full mechanism

The game stores defects in the save file in two distinct ways. Tool authors who only know about the first way will miss the cats covered by the second.

### Storage mechanism #1 — explicit sentinel in the cat's mutation table

Each cat has a flat array of 4-byte integers holding its visual mutation IDs (one per part slot: fur, body, head, tail, legs, arms, eyes, eyebrows, ears, mouth — with paired slots for left/right where applicable). When a cat is bred and inherits a defect from a parent, the game writes `0xFFFFFFFE` into the affected slot. This sentinel is also routed to a special "block tagged `-2`" entry inside each part-type's GON file (`eyes.gon`, `ears.gon`, etc.) which holds the human-readable description ("Eye Birth Defect: Blind, -1 STR" or similar).

A naive parser scans the table, finds `0xFFFFFFFE` at certain slots, looks them up in the GONs, and reports the defect. This works for ~17 cats in the reference save.

The same parser also catches defects whose mutation ID is a regular number that happens to live in a GON block tagged `birth_defect` — e.g. some leg-shape IDs are themselves marked as defects. Whommie's "Fur Birth Defect" is an example: the fur ID is a normal small integer, but the GON entry for that ID has `tag birth_defect`.

So far so good — these cats are easy to detect.

### Storage mechanism #2 — runtime computation from `headShape` and a SWF clip

For a subset of defects (eye, eyebrow, ear, mouth), the game stores **nothing on disk to indicate the defect**. The cat's mutation table holds normal part IDs at the affected slots. The defect signal is computed at runtime by the following pipeline:

1. The cat data structure includes a 1-byte field per part slot called the "part present" flag, sitting at offset `0x18` within each per-slot record. This byte is **not serialized to disk**. It exists only in memory.

2. When the game constructs a cat in memory, the constructor unconditionally sets all part-present flags to `1` (default: every part is present).

3. After deserializing the cat from the save, the game runs a function that consults the `CatHeadPlacements` SWF clip:
   - The clip is character ID `11007` inside the game's SWF resource bundle.
   - It is a multi-frame animation. Each frame represents one variant of head shape and accessories.
   - Distributed across frames are children with names matching the anchor set `{leye, reye, lear, rear, mouth, ahead, aneck, aface}`. These children mark where eye/ear/mouth body parts attach in the rendering.
   - The game seeks the clip to frame `headShape - 1` (note the off-by-one) and inspects the cumulative display list at that frame.
   - For each anchor name present in the display list, the corresponding `CatPart+0x18` flag is set to `1`. For each anchor name absent, the flag is set to `0`.
   - Eyebrow flags are then copied from eye flags (left from left, right from right) at the end of the loop. Eyebrows have no anchor of their own — they piggyback on the eye result.

4. When the game later builds the list of effects to display on the cat, a separate function reads the part-present flag for each slot. If the flag is zero, it emits `0xFFFFFFFE` (the same sentinel mechanism #1 uses) for that slot. Otherwise it emits the slot's normal part ID. The downstream display code is identical for both mechanisms — by the time defect text reaches the UI, you can't tell which mechanism produced it.

So a cat whose `headShape` happens to land on a frame where the SWF tag stream has temporarily removed (say) `reye` will display an Eye Birth Defect — even though the cat's mutation table on disk has a perfectly normal eye ID.

### Why specific head shapes produce the defect

The `CatHeadPlacements` SWF tag stream uses a specific encoding pattern at the boundaries of these defect-producing head shapes: at frame `N-1` it issues `RemoveObject2` to take an anchor child off the display list, and at frame `N` it re-places the anchor (with adjusted properties for the new head variant). Sequencing the remove and re-place in adjacent frames is a standard SWF technique for "swap one variant out, swap the next variant in".

The key insight is that `FUN_140734760` (the runtime function we replicate) seeks to `headShape - 1`. For head shape 304, that's frame 303 — exactly the frame where `reye` has been removed but not yet re-placed. Cats with `headShape = 304` see no `reye` anchor → CatPart flag goes to zero → eye + eyebrow defect.

For most head shapes, the seek lands on a frame far from any remove/re-place boundary, so the anchor set is the full set of 8 and no defect is produced. Only specific `headShape` values intersect a remove/re-place boundary, and the boundary determines which anchor goes missing:

| `headShape` (decimal) | Anchor missing at `headShape - 1` | Resulting defect(s) |
|---|---|---|
| 304 | `reye` | Eye + Eyebrow (right side, propagated) |
| 319 | `lear`, `rear` | Both ears |
| (others) | various, see SWF | various |

In the reference save: 15 cats out of 947 have a `headShape` that lands on a defect-producing frame.

### Why the off-by-one matters so much

Earlier reverse-engineering of the SWF compared the cumulative display list at the frame whose number matched `headShape` directly. Under that comparison, frame 99 (Kami) and frame 304 (Whommie) had **identical** anchor sets — because by frame 304 the re-place tag has already been applied. That gave the false impression that frame seek alone could not differentiate defect cats from clean cats.

The runtime function actually seeks one frame earlier, to `headShape - 1`. At that earlier frame, the re-place tag has not yet been applied, so the anchor is genuinely absent. Comparing at the right frame produces the right answer: frame 98 has all 8 anchors, frame 303 has 7 (missing `reye`), and the defect mechanism is fully explained.

Concretely:
- `headShape = 99`: seek to frame 98. Anchor set: `{aface, ahead, aneck, lear, leye, mouth, rear, reye}`. No defects.
- `headShape = 304`: seek to frame 303. Anchor set: `{aface, ahead, aneck, lear, leye, mouth, rear}`. Missing `reye` → eye+eyebrow defect.
- `headShape = 319`: seek to frame 318. Anchor set: `{aface, ahead, aneck, leye, mouth, reye}`. Missing `lear`+`rear` → ear defects.

---

## Performance notes

The `CatHeadPlacements` clip has 1505 frames. Computing the per-frame anchor sets correctly is fast if you do a single in-order pass (apply each tag once as you advance the frame counter, snapshot after each `ShowFrame`) — about 40 ms in Python on commodity hardware.

The naïve approach — re-walking from frame 0 for every snapshot — is O(N²) and takes roughly 30 seconds for the same data. Worth getting right.

Once computed, the per-frame list is small (≤8 anchor names per frame as a `frozenset` / `Set`). Cache it for the lifetime of your tool's session; only re-parse if the user changes the game's gpak path.

---

## Verification

A useful smoke test: after applying the fix, verify on the reference cats above that defect output matches in-game observation. The `reye` (right eye only) result for `headShape=304` is a particularly good check — naive implementations that don't handle the off-by-one or skip RemoveObject2 will produce visibly wrong results (no defects, or both eyes defective rather than right only).

If your tool reports a defect on every cat after the fix, you have probably set "no SWF data" to mean "all anchors missing" instead of "no synthesis". Make sure the empty-data fallback is empty-set, not full-set.
