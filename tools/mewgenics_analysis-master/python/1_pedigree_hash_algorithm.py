from common.dumped_save import DumpedSaveReader

SAVE_DUMP_PATH_PREFIX = '../out/dumped_save'

'''
Loads pedigree data structures and checks properties and hash values in order
to demonstrate manipulation over instances of parallel-hashmap's raw_hash_set.

polymeric 2026
'''

def hash_u64_fnv1a(key):
    digest = 0xcbf29ce484222325
    for i in range(8):
        byte = key >> (8 * i) & 0xff
        digest ^= byte
        digest *= 0x100000001b3
        digest &= 0xffff_ffff_ffff_ffff
    return digest

def hash_pair_u64_u64_fnv1a(kv):
    # Mewgenics 1.0.20695
    # 7ff701763aa0    int64_t maybe_fnv1a_hash_pair_u64_u64(int64_t eliminated_by_opt, uint128_t* data)
    fnv1a_digest_a = hash_u64_fnv1a(kv[0]) # r9
    fnv1a_digest_b = hash_u64_fnv1a(kv[1]) # rax

    return fnv1a_digest_a ^ fnv1a_digest_b # rax

def hash_u64_trivial(kv):
    # Mewgenics 1.0.20695
    # 7ff7017605d0    DecompTupleU64U64F64* maybe_retrieve_pedigree_record(int64_t* arg1, int64_t* kitten_sql_key)
    return kv[0]

def parallel_hashmap_apply_hash(kv, tbl_size_m1, hash_function):
    # Mewgenics 1.0.20695
    # 7ff701d4eee0    double maybe_score_coefficient_of_inbreeding(int64_t* arg1, int64_t parent_a_sql_key, int64_t parent_b_sql_key)
    stdhash_digest = hash_function(kv)

    mixed_digest = 0xde5fb9d2630458e9 * stdhash_digest
    mixed_digest = ((mixed_digest & 0xffff_ffff_ffff_ffff) + ((mixed_digest >> 64) & 0xffff_ffff_ffff_ffff)) & 0xffff_ffff_ffff_ffff

    h1_first_probe_idx = (mixed_digest >> 7) & tbl_size_m1
    h2_slot_fingerprint = mixed_digest & 0x7f

    return h1_first_probe_idx, h2_slot_fingerprint

def size_capacity_growth_verification(phmd):
    # assume we are working with a known version from decompilation
    assert(phmd.s_version == 0xFFFFFFFFFFFFFFF5)

    # assert trivial property on size vs capacity
    assert(phmd.size <= phmd.capacity)

    # assert trivial properties on lengths of what we scraped
    assert(phmd.capacity == len(phmd.hash_table))
    assert(phmd.capacity == len(phmd.data_table))

    # assert we understand how growth_left is calculated
    # -(-phmd.capacity * 7 // 8) == (phmd.capacity * 7).ceildiv(8)
    assert(-(-phmd.capacity * 7 // 8) - phmd.size == phmd.growth_left)

    # assert that size is the count of non-control bytes in the hash table
    assert(sum(map(lambda x: x <= 0x7f, phmd.hash_table)) == phmd.size)

def hash_verification(phmd, hash_function):
    data_in_first_probe_bucket = 0
    for i, (h, d) in enumerate(zip(phmd.hash_table, phmd.data_table)):
        if h <= 0x7f:
            h1_first_probe_idx, h2_slot_fingerprint = parallel_hashmap_apply_hash(d, phmd.capacity, hash_function)
            # assert that we computed H2 correctly
            assert(h2_slot_fingerprint == h)
            if i == h1_first_probe_idx:
                data_in_first_probe_bucket += 1
    # gauge that we computed H1 correctly by inspection (number looks correct by gut feeling)
    print(f'frac data in first probe bucket {data_in_first_probe_bucket / phmd.size:.02f}')

def main():
    save_reader = DumpedSaveReader(SAVE_DUMP_PATH_PREFIX)
    pedigree, coi_memos, accessible_cats = save_reader.read_pedigree(raw_view=True)

    size_capacity_growth_verification(pedigree)
    size_capacity_growth_verification(coi_memos)
    size_capacity_growth_verification(accessible_cats)

    hash_verification(pedigree, hash_u64_trivial)
    hash_verification(coi_memos, hash_pair_u64_u64_fnv1a)
    hash_verification(accessible_cats, hash_u64_trivial)

if __name__ == '__main__':
    main()
