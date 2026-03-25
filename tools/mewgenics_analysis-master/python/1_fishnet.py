from common.dumped_save import DumpedSaveReader
import networkx as nx
from pathlib import Path
import os

SAVE_DUMP_PATH_PREFIX = '../out/dumped_save'
OUT_PATH_PREFIX = '../out/fishnet'

'''
Writes pedigree information to a format that can be plotted by a network visualizer (e.g. Gephi, yEd).

polymeric 2026
'''

def main():
    save_reader = DumpedSaveReader(SAVE_DUMP_PATH_PREFIX)
    cats = save_reader.read_cats()
    pedigree, coi_memos, accessible_cats = save_reader.read_pedigree()

    # all_cat_ids = set(pedigree.keys()).union(set(cats.keys()))
    unpruned_cat_ids = set(pedigree.keys()).intersection(set(cats.keys()))

    g = nx.Graph()

    for id in unpruned_cat_ids:
        cat_info = cats[id] if id in cats else None
        name = cat_info.name() if cat_info else 'UNKNOWN'
        sex = cat_info.sex() if cat_info else 'UNKNOWN'
        g.add_node(id, label=name, sex=sex)

    for id in unpruned_cat_ids:
        pedigree_info = pedigree[id] if id in pedigree else None
        if pedigree_info:
            if pedigree_info.parent_a_id >= 0:
                g.add_edge(pedigree_info.parent_a_id, id, directed=True)
            if pedigree_info.parent_b_id >= 0:
                g.add_edge(pedigree_info.parent_b_id, id, directed=True)

    os.makedirs(OUT_PATH_PREFIX, exist_ok=True)
    # nx.write_gexf(g, Path(OUT_PATH_PREFIX, 'fishnet.gexf'))
    nx.write_graphml(g, Path(OUT_PATH_PREFIX, 'fishnet.graphml'))

if __name__ == '__main__':
    main()
