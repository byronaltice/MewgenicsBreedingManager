A loose collection of scripts and artifacts written to explore Mewgenics game data and implementation.

* **Amoeba** (cpp/amoeba): A dll hook that attaches to a Mewgenics game instance and provides tools for in-game data exploration and save logging.
* **ImHex patterns** (imhex_patterns/*): Human-readable patterns for parsing game structures, derived from decompilation, experimentation, and analysis.
* **Save parser and assertions** (python/dumped_save.py): Save parser written at parity with ImHex patterns. Assertions against properties and relationships between data fields.
    * (e.g. if this field is nonzero, does that mean the cat has a lover?).
* **Fun experiments**:
    * **python/0_dump_save.py** - dumps a save as individual binary files, to be examined at one's pleasure in a hex editor.
    * **python/1_cat_dump.py** - writes all known fields from every cat in a save to the console.
    * **python/1_fishnet.py** - exports a save's family trees to a graphml file for use in an external graphing tool.
    * **python/1_pedigree_hash_algorithm.py** - reverse engineering of the perigree store's hash implementations.
    * **python/1_verify_coi_calculation.py** - reverse engineering of the perigree store's COI calculations.
    * **python/2_amoeba_diff.py** - difference analyzer that lists which fields in which cats changed between two saves in an Amoeba stream.
