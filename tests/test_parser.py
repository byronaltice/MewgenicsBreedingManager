"""
Unit tests for save_parser module.
Run with: pytest tests/ -v
"""

import struct
import sys
import os
from types import SimpleNamespace

import pytest

# Ensure src/ directory is on the path so save_parser can be imported
_proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_src_dir = os.path.join(_proj_root, 'src')
sys.path.insert(0, _src_dir)
sys.path.insert(0, _proj_root)

from save_parser import (
    BinaryReader,
    _choose_age_from_creation_days,
    _valid_str,
    _normalize_gender,
    parse_save,
    _scan_blob_for_parent_uids,
    _resolve_parent_uids,
    can_breed,
    get_parents,
    get_grandparents,
    get_all_ancestors,
    find_common_ancestors,
    _ancestor_depths,
    _ancestor_contributions,
    _coi_from_contribs,
    _kinship,
    kinship_coi,
    risk_percent,
    _malady_breakdown,
    _combined_malady_chance,
    _is_hater_pair,
    shared_ancestor_counts,
    STAT_NAMES,
)

from breeding import (
    pair_key,
    is_hater_conflict,
    is_lover_conflict,
    is_mutual_lover_pair,
    trait_or_default,
    personality_score,
    is_direct_family_pair,
    evaluate_pair,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

class CatStub:
    """Minimal hashable Cat stub for testing without binary parsing."""

    def __init__(self, **kwargs):
        self.db_key = kwargs.get("db_key", 1)
        self.name = kwargs.get("name", "TestCat")
        self.gender = kwargs.get("gender", "male")
        self.sexuality = kwargs.get("sexuality", "straight")
        self.status = kwargs.get("status", "In House")
        self.room = kwargs.get("room", "Floor1_Large")
        self.generation = kwargs.get("generation", 0)
        self.parent_a = kwargs.get("parent_a", None)
        self.parent_b = kwargs.get("parent_b", None)
        self.children = kwargs.get("children", [])
        self.lovers = kwargs.get("lovers", [])
        self.haters = kwargs.get("haters", [])
        self.base_stats = kwargs.get("base_stats", {s: 4 for s in STAT_NAMES})
        self.total_stats = kwargs.get("total_stats", {s: 4 for s in STAT_NAMES})
        self.aggression = kwargs.get("aggression", 0.5)
        self.libido = kwargs.get("libido", 0.5)
        self.inbredness = kwargs.get("inbredness", 0.0)
        self.age = kwargs.get("age", 5)
        self.abilities = kwargs.get("abilities", [])
        self.passive_abilities = kwargs.get("passive_abilities", [])
        self.mutations = kwargs.get("mutations", [])
        self.disorders = kwargs.get("disorders", [])
        self.unique_id = kwargs.get("unique_id", "0x1")
        self.is_blacklisted = False
        self.must_breed = False

    def __hash__(self):
        """Make TestCat hashable so it can be used in sets and as dict keys."""
        return hash(self.db_key)

    def __eq__(self, other):
        """Compare CatStub objects by db_key."""
        if not isinstance(other, CatStub):
            return False
        return self.db_key == other.db_key

    def __repr__(self):
        return f"CatStub(db_key={self.db_key}, name={self.name!r})"


def _make_cat(**kwargs):
    """Create a minimal Cat-like stub for testing without binary parsing."""
    return CatStub(**kwargs)


# ── BinaryReader tests ───────────────────────────────────────────────────────

class TestBinaryReader:
    def test_u32(self):
        data = struct.pack('<I', 42)
        r = BinaryReader(data)
        assert r.u32() == 42
        assert r.pos == 4

    def test_i32_positive(self):
        data = struct.pack('<i', 100)
        r = BinaryReader(data)
        assert r.i32() == 100

    def test_i32_negative(self):
        data = struct.pack('<i', -5)
        r = BinaryReader(data)
        assert r.i32() == -5

    def test_u64(self):
        r = BinaryReader(struct.pack('<II', 100, 1))
        assert r.u64() == 100 + 4_294_967_296

    def test_u64_zero(self):
        r = BinaryReader(struct.pack('<II', 0, 0))
        assert r.u64() == 0

    def test_f64(self):
        r = BinaryReader(struct.pack('<d', 3.14))
        val = r.f64()
        assert abs(val - 3.14) < 1e-10

    def test_str_reads_utf8(self):
        payload = b"hello"
        data = struct.pack('<II', len(payload), 0) + payload
        r = BinaryReader(data)
        assert r.str() == "hello"
        assert r.pos == 8 + 5

    def test_str_empty(self):
        data = struct.pack('<II', 0, 0)
        r = BinaryReader(data)
        assert r.str() == ""

    def test_str_returns_none_on_overflow(self):
        data = struct.pack('<II', 99999, 0)
        r = BinaryReader(data)
        assert r.str() is None
        assert r.pos == 0  # position reset

    def test_utf16str(self):
        text = "Cat"
        encoded = text.encode('utf-16le')
        data = struct.pack('<II', len(text), 0) + encoded
        r = BinaryReader(data)
        assert r.utf16str() == "Cat"

    def test_skip(self):
        r = BinaryReader(b'\x00' * 100)
        r.skip(10)
        assert r.pos == 10

    def test_seek(self):
        r = BinaryReader(b'\x00' * 100)
        r.seek(50)
        assert r.pos == 50

    def test_remaining(self):
        r = BinaryReader(b'\x00' * 20, pos=5)
        assert r.remaining() == 15

    def test_remaining_at_end(self):
        r = BinaryReader(b'\x00' * 10, pos=10)
        assert r.remaining() == 0

    def test_sequential_reads(self):
        data = struct.pack('<IiI', 10, -20, 30)
        r = BinaryReader(data)
        assert r.u32() == 10
        assert r.i32() == -20
        assert r.u32() == 30
        assert r.remaining() == 0

    def test_init_with_pos(self):
        data = struct.pack('<II', 99, 42)
        r = BinaryReader(data, pos=4)
        assert r.u32() == 42


# ── Helper function tests ────────────────────────────────────────────────────

class TestValidStr:
    def test_normal_string(self):
        assert _valid_str("Fluffy") is True

    def test_none(self):
        assert _valid_str(None) is False

    def test_empty(self):
        assert _valid_str("") is False

    def test_none_string(self):
        assert _valid_str("none") is False
        assert _valid_str("None") is False
        assert _valid_str("NONE") is False

    def test_null_string(self):
        assert _valid_str("null") is False

    def test_defaultmove(self):
        assert _valid_str("defaultmove") is False
        assert _valid_str("DefaultMove") is False

    def test_default_move(self):
        assert _valid_str("default_move") is False

    def test_whitespace(self):
        assert _valid_str("  none  ") is False


class TestNormalizeGender:
    def test_male(self):
        assert _normalize_gender("male") == "male"

    def test_male_variant(self):
        assert _normalize_gender("maleX") == "male"
        assert _normalize_gender("Male") == "male"

    def test_female(self):
        assert _normalize_gender("female") == "female"

    def test_female_variant(self):
        assert _normalize_gender("femaleX") == "female"
        assert _normalize_gender("Female") == "female"

    def test_spidercat(self):
        assert _normalize_gender("spidercat") == "?"

    def test_none(self):
        assert _normalize_gender(None) == "?"

    def test_empty(self):
        assert _normalize_gender("") == "?"

    def test_unknown(self):
        assert _normalize_gender("something") == "?"


class TestChooseAgeFromCreationDays:
    def test_prefers_nonzero_creation_day_over_padding_zero(self):
        assert _choose_age_from_creation_days(69, [0, 57]) == 12

    def test_keeps_zero_when_it_is_the_only_candidate(self):
        assert _choose_age_from_creation_days(69, [0]) == 69

    def test_prefers_largest_valid_creation_day(self):
        assert _choose_age_from_creation_days(69, [1, 57, 12]) == 12


# ── Blob scanning tests ─────────────────────────────────────────────────────

class TestScanBlobForParentUids:
    def test_finds_both_parents(self):
        uid_a, uid_b = 1000, 2000
        # blob: skip 12 bytes, then two u64 UIDs
        blob = b'\x00' * 12 + struct.pack('<QQ', uid_a, uid_b) + b'\x00' * 1000
        result = _scan_blob_for_parent_uids(
            blob, frozenset({1000, 2000, 3000}), self_uid=3000
        )
        assert result == (1000, 2000)

    def test_finds_one_parent(self):
        blob = b'\x00' * 12 + struct.pack('<QQ', 1000, 0) + b'\x00' * 1000
        result = _scan_blob_for_parent_uids(
            blob, frozenset({1000, 2000}), self_uid=2000
        )
        assert result == (1000, 0)

    def test_finds_nothing_with_empty_uid_set(self):
        blob = b'\x00' * 1100
        result = _scan_blob_for_parent_uids(blob, frozenset(), self_uid=1)
        assert result == (0, 0)

    def test_ignores_self_uid(self):
        blob = b'\x00' * 12 + struct.pack('<QQ', 5000, 0) + b'\x00' * 1000
        result = _scan_blob_for_parent_uids(
            blob, frozenset({5000}), self_uid=5000
        )
        assert result == (0, 0)


# ── Breeding compatibility tests ─────────────────────────────────────────────

class TestCanBreed:
    def test_same_cat(self):
        cat = _make_cat(gender="male")
        ok, reason = can_breed(cat, cat)
        assert not ok
        assert "itself" in reason.lower()

    def test_opposite_gender_straight(self):
        a = _make_cat(db_key=1, gender="male", sexuality="straight")
        b = _make_cat(db_key=2, gender="female", sexuality="straight")
        ok, _ = can_breed(a, b)
        assert ok

    def test_same_gender_straight_rejected(self):
        a = _make_cat(db_key=1, gender="male", sexuality="straight")
        b = _make_cat(db_key=2, gender="male", sexuality="straight")
        ok, reason = can_breed(a, b)
        assert not ok

    def test_same_gender_gay_accepted(self):
        a = _make_cat(db_key=1, gender="male", sexuality="gay")
        b = _make_cat(db_key=2, gender="male", sexuality="gay")
        ok, _ = can_breed(a, b)
        assert ok

    def test_opposite_gender_gay_rejected(self):
        a = _make_cat(db_key=1, gender="male", sexuality="gay")
        b = _make_cat(db_key=2, gender="female", sexuality="straight")
        ok, reason = can_breed(a, b)
        assert not ok

    def test_bi_same_gender_rejected_against_straight(self):
        a = _make_cat(db_key=1, gender="male", sexuality="bi")
        b = _make_cat(db_key=2, gender="male", sexuality="straight")
        ok, reason = can_breed(a, b)
        assert not ok
        assert "straight" in reason.lower()

    def test_bi_opposite_gender_allowed(self):
        a = _make_cat(db_key=1, gender="male", sexuality="bi")
        b = _make_cat(db_key=2, gender="female", sexuality="straight")
        ok, _ = can_breed(a, b)
        assert ok

    def test_unknown_gender_pairs_with_any(self):
        a = _make_cat(db_key=1, gender="?")
        b = _make_cat(db_key=2, gender="female")
        ok, _ = can_breed(a, b)
        assert ok


# ── Ancestry / genetics tests ───────────────────────────────────────────────

class TestAncestry:
    def _build_family(self):
        """
        Build a simple family tree:
          grandpa + grandma -> dad
          dad + mom -> kitten
        """
        grandpa = _make_cat(db_key=1, name="Grandpa", generation=0)
        grandma = _make_cat(db_key=2, name="Grandma", generation=0)
        mom = _make_cat(db_key=3, name="Mom", generation=0)
        dad = _make_cat(db_key=4, name="Dad", generation=1,
                        parent_a=grandpa, parent_b=grandma)
        kitten = _make_cat(db_key=5, name="Kitten", generation=2,
                           parent_a=dad, parent_b=mom)
        return grandpa, grandma, mom, dad, kitten

    def test_get_parents(self):
        _, _, mom, dad, kitten = self._build_family()
        parents = get_parents(kitten)
        assert dad in parents
        assert mom in parents
        assert len(parents) == 2

    def test_get_parents_orphan(self):
        orphan = _make_cat(db_key=99, name="Orphan")
        assert get_parents(orphan) == []

    def test_get_grandparents(self):
        grandpa, grandma, _, _, kitten = self._build_family()
        gp = get_grandparents(kitten)
        assert grandpa in gp
        assert grandma in gp

    def test_get_all_ancestors(self):
        grandpa, grandma, mom, dad, kitten = self._build_family()
        ancestors = get_all_ancestors(kitten, depth=3)
        assert dad in ancestors
        assert mom in ancestors
        assert grandpa in ancestors
        assert grandma in ancestors

    def test_ancestor_depths(self):
        _, _, mom, dad, kitten = self._build_family()
        depths = _ancestor_depths(kitten, max_depth=4)
        assert depths[kitten] == 0
        assert depths[dad] == 1
        assert depths[mom] == 1

    def test_find_common_ancestors_unrelated(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert find_common_ancestors(a, b) == []

    def test_find_common_ancestors_siblings(self):
        dad = _make_cat(db_key=1, name="Dad")
        mom = _make_cat(db_key=2, name="Mom", gender="female")
        sibling_a = _make_cat(db_key=3, name="A", generation=1, parent_a=dad, parent_b=mom)
        sibling_b = _make_cat(db_key=4, name="B", generation=1, parent_a=dad, parent_b=mom)
        common = find_common_ancestors(sibling_a, sibling_b)
        assert dad in common
        assert mom in common

    def test_resolve_parent_uids_uses_pedigree_data_only(self):
        cat = SimpleNamespace(
            db_key=42,
            _uid_int=4200,
            _parent_uid_a=1111,
            _parent_uid_b=2222,
            _raw=b"ignored",
        )

        ped_map = {42: (7, None)}

        assert _resolve_parent_uids(cat, ped_map) == (7, None)

    def test_parse_save_marks_repaired_pedigree(self):
        cats, errors, rooms = parse_save(os.path.join(_proj_root, "tools", "saves", "23.sav"))
        chevy = next(cat for cat in cats if cat.db_key == 313)

        assert not errors
        assert chevy.parent_a is None and chevy.parent_b is None
        assert chevy.pedigree_was_repaired is True
        assert chevy.pedigree_cycle_breaks == 2


class TestInbreeding:
    def test_unrelated_minimal_risk(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B", gender="female")
        # Even unrelated cats have a base 2% disorder rate per game logic
        assert risk_percent(a, b) == pytest.approx(2.0)

    def test_siblings_nonzero_risk(self):
        dad = _make_cat(db_key=1, name="Dad")
        mom = _make_cat(db_key=2, name="Mom", gender="female")
        sibling_a = _make_cat(db_key=3, name="A", generation=1, parent_a=dad, parent_b=mom)
        sibling_b = _make_cat(db_key=4, name="B", gender="female", generation=1, parent_a=dad, parent_b=mom)
        risk = risk_percent(sibling_a, sibling_b)
        assert risk > 0.0

    def test_kinship_self(self):
        cat = _make_cat(db_key=1, name="Self")
        memo = {}
        k = _kinship(cat, cat, memo)
        # Kinship with self = (1 + F) / 2 = 0.5 for non-inbred
        assert abs(k - 0.5) < 1e-10

    def test_kinship_unrelated(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        memo = {}
        k = _kinship(a, b, memo)
        assert k == 0.0

    def test_kinship_siblings(self):
        dad = _make_cat(db_key=1, name="Dad", generation=0)
        mom = _make_cat(db_key=2, name="Mom", gender="female", generation=0)
        sib_a = _make_cat(db_key=3, name="A", generation=1, parent_a=dad, parent_b=mom)
        sib_b = _make_cat(db_key=4, name="B", gender="female", generation=1, parent_a=dad, parent_b=mom)
        memo = {}
        k = _kinship(sib_a, sib_b, memo)
        # Siblings with unrelated parents: kinship = 0.25
        assert abs(k - 0.25) < 1e-10

    def test_malady_breakdown_zero_coi(self):
        disorder, defect, combined = _malady_breakdown(0.0)
        assert abs(disorder - 0.02) < 1e-10
        assert defect == 0.0
        assert abs(combined - 0.02) < 1e-10

    def test_combined_malady_increases_with_coi(self):
        low = _combined_malady_chance(0.1)
        high = _combined_malady_chance(0.5)
        assert high > low

    def test_ancestor_contributions_orphan(self):
        cat = _make_cat(db_key=1, name="Orphan")
        contribs = _ancestor_contributions(cat)
        assert cat in contribs
        assert contribs[cat] == 1.0

    def test_coi_from_contribs_unrelated(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        ca = {a: 1.0}
        cb = {b: 1.0}
        assert _coi_from_contribs(ca, cb) == 0.0

    def test_shared_ancestor_counts_unrelated(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        total, recent = shared_ancestor_counts(a, b)
        assert total == 0
        assert recent == 0


class TestIsHaterPair:
    def test_no_hate(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert not _is_hater_pair(a, b)

    def test_a_hates_b(self):
        b = _make_cat(db_key=2, name="B")
        a = _make_cat(db_key=1, name="A", haters=[b])
        assert _is_hater_pair(a, b)

    def test_b_hates_a(self):
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B", haters=[a])
        assert _is_hater_pair(a, b)


# ── Breeding module tests ───────────────────────────────────────────────────

class TestBreedingHelpers:
    def test_pair_key_normalized(self):
        a = _make_cat(db_key=5, name="A")
        b = _make_cat(db_key=3, name="B")
        assert pair_key(a, b) == (3, 5)
        assert pair_key(b, a) == (3, 5)

    def test_trait_or_default_none(self):
        assert trait_or_default(None) == 0.5

    def test_trait_or_default_value(self):
        assert trait_or_default(0.8) == 0.8

    def test_trait_or_default_clamp_high(self):
        assert trait_or_default(1.5) == 1.0

    def test_trait_or_default_clamp_low(self):
        assert trait_or_default(-0.5) == 0.0

    def test_is_hater_conflict(self):
        hater_map = {1: {2}, 2: set()}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert is_hater_conflict(a, b, hater_map)

    def test_no_hater_conflict(self):
        hater_map = {1: set(), 2: set()}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert not is_hater_conflict(a, b, hater_map)

    def test_is_lover_conflict_when_avoiding(self):
        lover_map = {1: {3}, 2: set()}  # cat 1 loves cat 3, not cat 2
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert is_lover_conflict(a, b, lover_map, avoid_lovers=True)

    def test_no_lover_conflict_when_not_avoiding(self):
        lover_map = {1: {3}, 2: set()}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert not is_lover_conflict(a, b, lover_map, avoid_lovers=False)

    def test_is_mutual_lover_pair(self):
        lover_map = {1: {2}, 2: {1}}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert is_mutual_lover_pair(a, b, lover_map)

    def test_not_mutual_lover_pair(self):
        lover_map = {1: {2}, 2: set()}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert not is_mutual_lover_pair(a, b, lover_map)

    def test_is_direct_family_parent_child(self):
        parent_key_map = {1: set(), 2: {1}}  # cat 2's parent is cat 1
        a = _make_cat(db_key=1, name="Dad")
        b = _make_cat(db_key=2, name="Kitten")
        assert is_direct_family_pair(a, b, parent_key_map)

    def test_is_direct_family_siblings(self):
        parent_key_map = {1: {3, 4}, 2: {3, 4}}  # share parents
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert is_direct_family_pair(a, b, parent_key_map)

    def test_not_direct_family(self):
        parent_key_map = {1: {3}, 2: {4}}
        a = _make_cat(db_key=1, name="A")
        b = _make_cat(db_key=2, name="B")
        assert not is_direct_family_pair(a, b, parent_key_map)

    def test_personality_score_low_aggression(self):
        cat = _make_cat(db_key=1, name="A", aggression=0.0)
        score = personality_score([cat], prefer_low_aggression=True, prefer_high_libido=False)
        assert score == 1.0  # 1.0 - 0.0 = 1.0

    def test_personality_score_high_libido(self):
        cat = _make_cat(db_key=1, name="A", libido=1.0)
        score = personality_score([cat], prefer_low_aggression=False, prefer_high_libido=True)
        assert score == 1.0

    def test_evaluate_pair_basic(self):
        a = _make_cat(db_key=1, name="A", gender="male")
        b = _make_cat(db_key=2, name="B", gender="female")
        hater_map = {1: set(), 2: set()}
        lover_map = {1: set(), 2: set()}
        ok, reason, risk = evaluate_pair(
            a, b,
            hater_key_map=hater_map,
            lover_key_map=lover_map,
            avoid_lovers=False,
        )
        assert ok
        assert reason == ""

    def test_evaluate_pair_with_cache(self):
        a = _make_cat(db_key=1, name="A", gender="male")
        b = _make_cat(db_key=2, name="B", gender="female")
        hater_map = {1: set(), 2: set()}
        lover_map = {1: set(), 2: set()}
        cache_dict: dict = {}
        # First call
        ok1, _, _ = evaluate_pair(
            a, b,
            hater_key_map=hater_map,
            lover_key_map=lover_map,
            avoid_lovers=False,
            pair_eval_cache=cache_dict,
        )
        assert ok1
        assert len(cache_dict) == 1
        # Second call should use cache
        ok2, _, _ = evaluate_pair(
            a, b,
            hater_key_map=hater_map,
            lover_key_map=lover_map,
            avoid_lovers=False,
            pair_eval_cache=cache_dict,
        )
        assert ok2
