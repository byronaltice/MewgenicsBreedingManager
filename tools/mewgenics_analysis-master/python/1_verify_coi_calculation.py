from common.dumped_save import DumpedSaveReader
from collections import deque

SAVE_DUMP_PATH_PREFIX = '../out/dumped_save'

'''
Sketch that recomputes coefficient of inbreeding and checks against oracle values from the save.

polymeric 2026
'''

def compute_all_cois(pedigree):
    # S0: Topological sort to order ancestors before descendants
    s0_indegrees = {id: 0 for id in pedigree.keys()}
    for id in s0_indegrees.keys():
        node = pedigree[id]
        for parent_id in [node.parent_a_id, node.parent_b_id]:
            if parent_id >= 0:
                s0_indegrees[parent_id] += 1

    s0_workqueue = deque([k for k, v in s0_indegrees.items() if v == 0])
    s1_workqueue = deque([])
    while s0_workqueue:
        id = s0_workqueue.popleft()
        node = pedigree[id]
        s1_workqueue.appendleft(id)
        for parent_id in [node.parent_a_id, node.parent_b_id]:
            if parent_id >= 0:
                s0_indegrees[parent_id] -= 1
                if s0_indegrees[parent_id] == 0:
                    s0_workqueue.append(parent_id)

    # S1: Annotate COIs
    s1_coi = {}
    for id in s1_workqueue:
        # COI_child := sum_COMMONANCESTORS=ca(0.5**(path_through_parent_a_to_ca+path_through_parent_b_to_ca-1) * (1 + COI_ca))
        # where for each COMMONANCESTORS=ca, path_through_parent_a_to_ca intersect path_through_parent_b_to_ca == {ca}
        node = pedigree[id]
        if node.parent_a_id == -1 or node.parent_b_id == -1:
            s1_coi[id] = 0.0
        else:
            # Stupid implementation: find common ancestors by set-intersecting all fan-ins to parent_a and parent_b
            # Inbreeding loops are identified as pairs of paths that set-intersect with exactly one common member
            # and which both end at that common member. That common set member is called the "common ancestor".
            # There is a 1-1 correspondence between loops and the common ancestor at the top of each loop.
            def list_fanins(id):
                witnessed = set()
                # current_node, accumulated_path
                workstack = deque([(id,)])
                while workstack:
                    path = workstack.pop()
                    if path in witnessed:
                        continue
                    else:
                        witnessed.add(path)
                        last_node = pedigree[path[-1]]
                        if last_node.parent_a_id >= 0:
                            path_plus = (*path, last_node.parent_a_id)
                            workstack.append(path_plus)
                        if last_node.parent_b_id >= 0:
                            path_plus = (*path, last_node.parent_b_id)
                            workstack.append(path_plus)
                return witnessed

            fanins_parent_a = list_fanins(node.parent_a_id)
            fanins_parent_b = list_fanins(node.parent_b_id)

            # Find all common ancestors and push their COI and the loop length to a list
            common_ancestors = []
            for fanin_a in fanins_parent_a:
                set_fanin_a = set(fanin_a)
                for fanin_b in fanins_parent_b:
                    set_fanin_b = set(fanin_b)
                    intersection = set_fanin_a.intersection(set_fanin_b)
                    if len(intersection) == 1 and fanin_a[-1] == fanin_b[-1]:
                        ca_id = fanin_a[-1]
                        ca_coi = s1_coi[ca_id]
                        # total loop members excluding child node
                        generational_exponent = len(fanin_a) + len(fanin_b) - 1
                        common_ancestors.append((ca_id, ca_coi, generational_exponent))

            # Now compute the kitten's COI
            coi = 0.0
            for ca_info in common_ancestors:
                ca_id, ca_coi, generational_exponent = ca_info
                coi += 0.5 ** generational_exponent * (1 + ca_coi)
            s1_coi[id] = coi
    return s1_coi

def map_name(cats, id):
    if id in cats:
        return cats[id].name()
    elif id == -1:
        return "ROOT"
    else:
        return "UNKNOWN"

def map_coi(coi):
    if coi >= 0.25:
        return 'slightly'
    elif coi >= 0.50:
        return 'moderately'
    elif coi >= 0.80:
        return 'highly'
    else:
        return 'not'

def main():
    save_reader = DumpedSaveReader(SAVE_DUMP_PATH_PREFIX)
    cats = save_reader.read_cats()
    pedigree, coi_memos, accessible_cats = save_reader.read_pedigree()

    cois = compute_all_cois(pedigree)
    for k, v in pedigree.items():
        our_coi = cois[k]
        their_coi = v.coi
        # check the coi value stored in the pedigree structure vs. ours
        if our_coi != their_coi:
            print('FAIL', our_coi, their_coi)
            raise Exception

    for k, v in sorted(cats.items()):
        pedigree_info = pedigree[k]
        # check the coi field stored in the cat structure vs. ours
        assert(pedigree_info.coi == v.coi())
        parent_a = map_name(cats, pedigree_info.parent_a_id)
        parent_b = map_name(cats, pedigree_info.parent_b_id)
        our_coi = cois[k]
        print(f'{v.name()} ({our_coi:.2f}, {map_coi(our_coi)} inbred) <- {parent_a} * {parent_b}')

if __name__ == '__main__':
    main()
