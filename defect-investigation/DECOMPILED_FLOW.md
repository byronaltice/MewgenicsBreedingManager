# Decompiled Flow

A consolidated mermaid view of what we know about Mewgenics' cat-loading, defect-display, and breeding-time defect-application pipelines, drawn from Directions 29–48.

The diagram uses readable names. The map at the bottom resolves each readable name to the underlying `FUN_xxxxxxxx` symbol or data address from `findings/binary_function_map.md`.

```mermaid
flowchart TD
    %% ======================================================================
    %% Game session bootstrap
    %% ======================================================================
    subgraph SESSION_BOOT[Session bootstrap]
        SAVECTX_LOAD[Load_SaveFileCat_Context] -->|reads SQLite properties.random_seed| RNG_SEED[Seed_xoshiro256_at_TLS+0x178]
    end

    %% ======================================================================
    %% Per-cat lazy load chain (Direction 45)
    %% ======================================================================
    subgraph PER_CAT_LOAD[Per-cat lazy load chain]
        direction TB
        GET_CAT[Get_Cat_By_DBKey] --> ALLOC[Alloc 0xc58 + memset 0]
        ALLOC --> CAT_CTOR[CatData_Constructor]
        CAT_CTOR --> CONTAINER_CTOR[BodyPart_Container_Constructor<br/>writes CatPart+0x18 = 1 for all 19 parts]
        CONTAINER_CTOR --> ROSTER_LOAD[MewSaveFile_Load_Roster]

        ROSTER_LOAD --> RNG_SAVE[Save TLS RNG state]
        RNG_SAVE --> DEFAULT_INIT[Cat_Default_Initializer]

        DEFAULT_INIT --> RANDOMIZE_PARTS[Randomize_BodyParts_From_GON]
        RANDOMIZE_PARTS --> REROLL_VOICE[Reroll_Voice]
        REROLL_VOICE --> PLACE_PRE[Placement_Reconstruction&nbsp;#40;pre-deserialize#41;]

        PLACE_PRE --> STORE_DBKEY[Store db_key on CatData]
        STORE_DBKEY --> SQLITE_READ[SQLite read cats blob]
        SQLITE_READ --> DESERIALIZE[Serialize_CatData<br/>read mode]
        DESERIALIZE --> PLACE_POST[Placement_Reconstruction&nbsp;#40;post-deserialize#41;]
        PLACE_POST --> RNG_RESTORE[Restore TLS RNG state]
    end

    SAVECTX_LOAD -.->|first time only| GET_CAT

    %% ======================================================================
    %% Placement reconstruction internals (Directions 47, 48)
    %% ======================================================================
    subgraph PLACEMENT_INTERNALS[Placement_Reconstruction internals]
        direction TB
        CLEAR_FLAGS[Clear facial/attached CatPart+0x18 flags<br/>eyes, ears, mouth, ahead, aneck, aface] --> LOAD_PLACEMENT[Load CatHeadPlacements MovieClip<br/>char_id=11007 in catparts.swf]
        LOAD_PLACEMENT --> SELECT_FRAME[Select frame N = saved head shape ID]
        SELECT_FRAME --> ITER_ANCHORS{Iterate anchor children}
        ITER_ANCHORS -->|leye / reye| SET_EYE[Set eye CatPart+0x18 = 1]
        ITER_ANCHORS -->|lear / rear| SET_EAR[Set ear CatPart+0x18 = 1]
        ITER_ANCHORS -->|mouth| SET_MOUTH[Set mouth flag = 1]
        ITER_ANCHORS -->|ahead / aneck / aface| SET_ATTACH[Set attached-part flags = 1]
        SET_EYE --> COPY_EYEBROWS[Copy eye records to eyebrow records]

        UNKNOWN_WALK[Open question Direction 49:<br/>does iteration walk outer clip's display list,<br/>or descend into per-frame depth=1 sub-clip?]
        SELECT_FRAME -.-> UNKNOWN_WALK
    end

    PLACE_PRE -. uses .-> PLACEMENT_INTERNALS
    PLACE_POST -. uses .-> PLACEMENT_INTERNALS

    %% ======================================================================
    %% Effective-mutation display chain (Direction 42)
    %% ======================================================================
    subgraph DISPLAY_CHAIN[Effective-mutation / tooltip display]
        direction TB
        BUILD_EFFECTIVE[Build_Effective_Mutation_List] -->|reads CatPart+0x18| FLAG_CHECK{Flag == 0?}
        FLAG_CHECK -->|yes| SUB_FFFFFFFE[Effective part ID := 0xFFFFFFFE]
        FLAG_CHECK -->|no| KEEP_PART[Keep saved part ID]
        SUB_FFFFFFFE --> TOOLTIP[Tooltip_Builder]
        KEEP_PART --> TOOLTIP
        TOOLTIP --> LOOKUP[Mutation_Entry_Lookup_By_PartID]
        LOOKUP -->|0xFFFFFFFE| GON_BLOCK_M2[GON block -2: tag birth_defect]
        GON_BLOCK_M2 --> SHOW_DEFECT[Show BirthDefectTooltip]
    end

    PLACE_POST --> BUILD_EFFECTIVE

    %% ======================================================================
    %% Breeding-time defect application (Direction 43, ruled out for unresolved cases)
    %% ======================================================================
    subgraph BREED_PATH[Breeding-time path]
        direction TB
        BREED[CatData_Breed] --> READ_PARENT_DEFECTS[Read_Parent_Defect_Strings]
        READ_PARENT_DEFECTS --> APPLY_PARENT_DEFECTS[Apply_Parent_Defect_Effects<br/>writes effect-list + GON effects]
        BREED --> INHERIT_PARTS[BodyPart_Inheritance_Helper]
        INHERIT_PARTS -->|if CatPart+0x18 == 0| SUB_FFFFFFFE2[Substitute 0xFFFFFFFE for GON lookup]
        BREED --> ROLL_DEFECT[Birth_Defect_Candidate_Roller]
        ROLL_DEFECT -->|loads from| CAND_TABLE[(_DAT_141130700: 0,1,2,3,3,3,3,3,8,8<br/>body/head/tail/rear-legs/front-legs only)]
        ROLL_DEFECT --> APPLY_DEFECT[Apply_Defect_Lambda]
        APPLY_DEFECT --> WRITE_PART_ID[Part_ID_Writer<br/>writes visible ID, NOT +0x18]
    end

    %% ======================================================================
    %% Save-file progression milestone path (Direction 43, gated off in our save)
    %% ======================================================================
    subgraph PROGRESSION_PATH[Save-file progression milestone path]
        COMPUTE_PCT[Compute_SaveFile_Percentage] -->|when save_file_percent crosses next_cat_mutation| ROLL_DEFECT
        COMPUTE_PCT -.->|gated off in investigation save| GATED((No-op))
    end

    %% ======================================================================
    %% Cross-edges
    %% ======================================================================
    RNG_SEED -. seeds .-> ROLL_DEFECT
    RNG_SEED -. seeds .-> RANDOMIZE_PARTS
    RNG_SEED -. seeds .-> REROLL_VOICE

    %% ======================================================================
    %% Styling
    %% ======================================================================
    classDef confirmed fill:#1f3b1f,stroke:#3aa55a,color:#dff,stroke-width:1px;
    classDef ruled_out fill:#3b1f1f,stroke:#a53a3a,color:#fdd,stroke-width:1px;
    classDef open fill:#3b321f,stroke:#a5853a,color:#ffd,stroke-width:1px;
    classDef data fill:#1f2b3b,stroke:#3a6aa5,color:#ddf,stroke-width:1px;

    class GET_CAT,ALLOC,CAT_CTOR,CONTAINER_CTOR,ROSTER_LOAD,RNG_SAVE,DEFAULT_INIT,RANDOMIZE_PARTS,REROLL_VOICE,PLACE_PRE,STORE_DBKEY,SQLITE_READ,DESERIALIZE,PLACE_POST,RNG_RESTORE,SAVECTX_LOAD,RNG_SEED confirmed;
    class CLEAR_FLAGS,LOAD_PLACEMENT,SELECT_FRAME,ITER_ANCHORS,SET_EYE,SET_EAR,SET_MOUTH,SET_ATTACH,COPY_EYEBROWS confirmed;
    class BUILD_EFFECTIVE,FLAG_CHECK,SUB_FFFFFFFE,KEEP_PART,TOOLTIP,LOOKUP,GON_BLOCK_M2,SHOW_DEFECT confirmed;
    class BREED,READ_PARENT_DEFECTS,APPLY_PARENT_DEFECTS,INHERIT_PARTS,SUB_FFFFFFFE2,ROLL_DEFECT,APPLY_DEFECT,WRITE_PART_ID confirmed;
    class CAND_TABLE data;
    class COMPUTE_PCT,GATED ruled_out;
    class UNKNOWN_WALK open;
```

Legend: green = confirmed in the binary, red = ruled out / no-op for the unresolved defect cases, yellow = open question, blue = data table.

## Readable name → low-level symbol map

### Session bootstrap
| Readable name | Symbol / address |
|---|---|
| Load_SaveFileCat_Context | `FUN_140230750` (`glaiel::MewSaveFile::Load(__int64, SaveFileCat&)`) |
| Seed_xoshiro256_at_TLS+0x178 | TLS slot `+0x178`, seeded from SQLite `properties.random_seed` |

### Per-cat lazy load chain
| Readable name | Symbol |
|---|---|
| Get_Cat_By_DBKey | `FUN_1400d5600` (`get_cat_by_db_key`) |
| CatData_Constructor | `FUN_14005dd60` |
| BodyPart_Container_Constructor | `FUN_14005dfd0` |
| MewSaveFile_Load_Roster | `FUN_14022dfb0` (`glaiel::MewSaveFile::Load(__int64, CatData&)`) |
| Cat_Default_Initializer | `FUN_1400b5260` |
| Randomize_BodyParts_From_GON | `FUN_140732750` |
| Reroll_Voice | `FUN_140733100` (`glaiel::CatVisuals::reroll_voice(Gender)`) |
| Placement_Reconstruction | `FUN_140734760` |
| Serialize_CatData | `FUN_14022d360` (`glaiel::SerializeCatData`) |

### Placement_Reconstruction internals
| Readable name | Symbol / resource |
|---|---|
| CatHeadPlacements MovieClip | `DefineSprite` `char_id=11007` in `game-files/resources/gpak-video/swfs/catparts.swf` |
| Anchor strings | `"leye"`, `"reye"`, `"lear"`, `"rear"`, `"mouth"`, `"ahead"`, `"aneck"`, `"aface"` |

### Effective-mutation / tooltip display
| Readable name | Symbol |
|---|---|
| Build_Effective_Mutation_List | `FUN_1400c9810` |
| Tooltip_Builder | `FUN_1400e38c0` |
| Mutation_Entry_Lookup_By_PartID | `FUN_1407b1190` |

### Breeding-time path
| Readable name | Symbol |
|---|---|
| CatData_Breed | `FUN_1400a6790` (`glaiel::CatData::breed`) |
| Read_Parent_Defect_Strings | `FUN_1400c17f0` (calls `FUN_1400c1600`) |
| Apply_Parent_Defect_Effects | `FUN_1400c1ac0` |
| BodyPart_Inheritance_Helper | `FUN_1400a5390` |
| Birth_Defect_Candidate_Roller | `FUN_1400ca4a0` |
| Apply_Defect_Lambda | `FUN_1400caa20` (`CatData::MutatePiece(...)::lambda_1`) |
| Part_ID_Writer | `FUN_1400cb130` |
| Birth-defect candidate table | `_DAT_141130700` (entries: 0, 1, 2, 3, 3, 3, 3, 3, 8, 8) |

### Save-file progression milestone path
| Readable name | Symbol |
|---|---|
| Compute_SaveFile_Percentage | `FUN_1401d2ff0` (`GlobalProgressionData::ComputeSaveFilePercentage`) |

### Save serializer building blocks (referenced from Serialize_CatData)
| Readable name | Symbol |
|---|---|
| BodyPart_Container_Serializer | `FUN_14022ce10` (writes 73 u32s; calls per-part serializer 14×) |
| Per_BodyPart_Serializer | `FUN_14022cd00` (writes 5 u32s — does NOT serialize `+0x18`) |
| Stat_Record_Serializer | `FUN_14022cf90` (`stat_base`, `stat_mod`, `stat_sec`) |
| Variable_List_Serializer | `FUN_14022d100` |
| Equipment_Slot_Serializer | `FUN_14022b1f0` |
| Generic_ByteVector_Serializer | `FUN_1402345e0` (`CatData+0x8`) |

## Key invariants to remember

- `CatPart+0x18` is the runtime "present" flag. It is **not** serialized (Direction 33). It is written to `1` by the container constructor for all 19 parts, then selectively cleared/set by `Placement_Reconstruction`.
- The display chain has **no fallback path**: a defect tooltip is only shown when `0xFFFFFFFE` is substituted, which requires `CatPart+0x18 == 0`.
- `Birth_Defect_Candidate_Roller` covers only body/head/tail/rear-legs/front-legs categories (per `_DAT_141130700`). It cannot produce eye/eyebrow/ear defects, which is why Whommie's eye/eyebrow defects and Bud's ear defect must come from a different mechanism — currently believed to be `Placement_Reconstruction`.
- The save-file progression milestone path is gated off in the investigation save (`save_file_percent=80 < next_cat_mutation=90`) and could not have produced the unresolved defects regardless.
