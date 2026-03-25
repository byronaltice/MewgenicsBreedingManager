#pragma once

#include <cstdint>

// Homemade knock-off of parallel-hashmap's flat_hash_map/raw_hash_set.
// It carries that infamous compiled-with-MSVC aftertaste, no matter where it's taken!
//
// polymeric 2026

#ifdef _MSC_VER
#include <intrin.h>
#pragma intrinsic(_umul128)
inline uint64_t umul128_and_mix(uint64_t a, uint64_t b) {
    uint64_t high;
    uint64_t low = _umul128(a, b, &high);
    return high + low;
}
#define NO_UNIQUE_ADDRESS [[msvc::no_unique_address]]
#else
inline uint64_t umul128_and_mix(uint64_t a, uint64_t b) {
    __uint128_t product = static_cast<__uint128_t >(a) * static_cast<__uint128_t>(b);
    return static_cast<uint64_t >(product >> 64) + static_cast<uint64_t >(product);
}
#define NO_UNIQUE_ADDRESS [[no_unique_address]]
#endif

// Sets are maps implemented with an empty V
struct PhmapEmpty {};

template<typename K, typename V>
struct PhmapCompressedPair {
    NO_UNIQUE_ADDRESS K key;
    NO_UNIQUE_ADDRESS V val;
};

// To implement for a particular parameter K, a hasher
// of the following form must be provided as parameter H
// struct KHasher {
//     static uint64_t hash(K *key) { return /**/; }
//     static bool identical(K *key1, K *key2) { return /**/; }
// };

template<typename K, typename V, typename H>
struct PhmapFlatHashSap {
    uint8_t *ctrl;
    PhmapCompressedPair<K, V> *slots;
    size_t size;
    size_t cap;
    // HashtablezInfoHandle is a ZST, 1 overhead byte + 7 padding bytes
    uint64_t infoz_overhead_;
    // settings_ contains three ZSTs declared after growth_left
    // Due to the nature of the MSVC std::tuple used to implement settings_,
    // the ZSTs are are placed before growth_left in memory and consume
    // 3 bytes of overhead + 5 padding bytes
    uint64_t settings_overhead_;
    size_t growth_left;

    // delete the copy constructor to block implicit copying
    PhmapFlatHashSap(const PhmapFlatHashSap&) = delete;
    PhmapFlatHashSap& operator=(const PhmapFlatHashSap&) = delete;

    uint64_t calculate_h12(K *key) {
        uint64_t digest = H::hash(key);
        digest = umul128_and_mix(digest, 0xde5fb9d2630458e9);
        return digest;
    }

    // Perform a lookup by sequentially comparing full keys behind occupied slots.
    // Relies on correct implementation of H::identical. H::hash is not used.
    // PhmapCompressedPair<K, V> *get_linear_scan(K *key) {
    //     for(size_t i = 0; i < this->cap; i++) {
    //         if(this->ctrl[i] <= 0x7F && H::identical(key, &this->slots[i].key)) {
    //             return &this->slots[i];
    //         }
    //     }
    //     return nullptr;
    // }

    // Perform a lookup by hash probing, using a linear probe sequence.
    // Relies on correct implementations of H::hash and H::identical.
    // PhmapCompressedPair<K, V> *get_linear_hash(K *key) {
    //     uint64_t h = calculate_h12(key);
    //     size_t h1_first_probe_idx = (h >> 7) & this->cap;
    //     uint8_t h2_slot_fingerprint = h & 0x7f;
    //     size_t probe_idx = h1_first_probe_idx;

    //     // Relies on more specific details of the hash map's design
    //     // than get_linear_scan(), but fewer than get().
    //     // Kept as a fallback implementation for debugging.

    //     do {
    //         if (this->ctrl[probe_idx] == h2_slot_fingerprint) {
    //             if(H::identical(key, &this->slots[probe_idx].key)) {
    //                 return &this->slots[probe_idx];
    //             }
    //         }
    //         probe_idx = (probe_idx + 1) % this->cap;
    //     } while(probe_idx != h1_first_probe_idx);
    //     return nullptr;
    // }

    // Perform a lookup by hash probing, using the designed probe sequence.
    // Relies on correct implementations of H::hash and H::identical.
    PhmapCompressedPair<K, V> *get(K *key) {
        uint64_t h = calculate_h12(key);
        size_t h1_first_probe_idx = (h >> 7) & this->cap;
        uint8_t h2_slot_fingerprint = h & 0x7f;
        size_t probe_idx_offset = h1_first_probe_idx;

        // Follows the probing schedule described in "IMPLEMENTATION DETAILS" of phmap.h
        // NB, H1 determines the framing of the probe groups.
        // H1 is truncated "modulo (capacity + 1)" to determine the first control index.
        // That is to say, the first control entry tested is ctrl[H1 % (cap + 1)], not ctrl[(H1 % (cap + 1)) / 16 * 16]
        // https://github.com/greg7mdp/parallel-hashmap/blob/8442f1c82cad04c026e3db4959c6b7a5396f982a/parallel_hashmap/phmap.h

        size_t quadratic_generation = 0;
        while(true) {
            bool has_empty = false;
            for(int i = 0; i < 16; i++) {
                if (this->ctrl[probe_idx_offset + i] == h2_slot_fingerprint) {
                    // need to normalize idx because we can walk into the cloned part of ctrl
                    size_t slot_idx = (probe_idx_offset + i) & this->cap;
                    if(H::identical(key, &this->slots[slot_idx].key)) {
                        return &this->slots[slot_idx];
                    }
                } else if(this->ctrl[probe_idx_offset + i] == 0x80) {
                    has_empty = true;
                }
            }
            if(has_empty) {
                break;
            }
            quadratic_generation++;
            probe_idx_offset = (probe_idx_offset + quadratic_generation * 16) & this->cap;
            if (probe_idx_offset == h1_first_probe_idx) {
                break;
            }
        }
        return nullptr;
    }

    // bool verify_get_linear_scan() {
    //     for(size_t i = 0; i < this->cap; i++) {
    //         if(ctrl[i] <= 0x7F) {
    //             bool get_found = &this->slots[i] == this->get_linear_scan(&this->slots[i].key);
    //             if(!get_found) {
    //                 return false;
    //             }
    //         }
    //     }
    //     return true;
    // }

    // bool verify_get_linear_hash() {
    //     for(size_t i = 0; i < this->cap; i++) {
    //         if(ctrl[i] <= 0x7F) {
    //             bool get_found = &this->slots[i] == this->get_linear_hash(&this->slots[i].key);
    //             if(!get_found) {
    //                 return false;
    //             }
    //         }
    //     }
    //     return true;
    // }

    bool verify_get() {
        for(size_t i = 0; i < this->cap; i++) {
            if(ctrl[i] <= 0x7F) {
                bool get_found = &this->slots[i] == this->get(&this->slots[i].key);
                if(!get_found) {
                    return false;
                }
            }
        }
        return true;
    }

    // this is probably enough... no SIMD acceleration, no write support, not battle-tested
    // but it captures a raw_hash_set layout almost as grandma (MSVC 2022) would've made it
};
