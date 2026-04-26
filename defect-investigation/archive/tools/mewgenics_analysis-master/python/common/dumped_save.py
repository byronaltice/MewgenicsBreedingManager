from pathlib import Path
from collections import namedtuple
import struct

CatPedigree = namedtuple('CatPedigree', ['child_id', 'parent_a_id', 'parent_b_id', 'coi'])
CatCoiMemo = namedtuple('CatCoiMemo', ['parent_a_id', 'parent_b_id', 'coi'])

BodyPartDescriptor = namedtuple('BodyPartDescriptor', ['part_sprite_idx', 'texture_sprite_idx', 'unknown_0', 'unknown_1_nonzero_on_arms_and_legs', 'unknown_2'])
BodyParts = namedtuple('BodyParts', ['texture_sprite_idx', 'heritable_palette_idx', 'collar_palette_idx', 'body', 'head', 'tail', 'leg1', 'leg2', 'arm1', 'arm2', 'lefteye', 'righteye', 'lefteyebrow', 'righteyebrow', 'leftear', 'rightear', 'mouth', 'unknown_0', 'unknown_1', 'voice', 'pitch'])
CatStats = namedtuple('CatStats', ['str', 'dex', 'con', 'int', 'spd', 'cha', 'lck'])
Injuries = namedtuple('Injuries', ['broken_paw', 'torn_tendon', 'broken_rib', 'concussion', 'disfigured', 'broken_leg', 'jinxed', 'immolated', 'exsanguinated', 'poisoned', 'cursed', 'radiated', 'unused_0', 'unused_1', 'unused_2', 'unused_3'])
CampaignStats = namedtuple('CampaignStats', ['hp', 'dead', 'unknown_0', 'unknown_1', 'event_stat_modifiers'])
# PassiveAbility = namedtuple('PassiveAbility', ['name', 'unknown_0'])
Equipment = namedtuple('Equipment', ['version', 'has_equipment', 'name', 'unknown_0', 'unknown_1', 'unknown_2', 'unknown_3', 'unknown_4', 'unknown_5', 'unknown_6'])
Kit = namedtuple('Kit', ['head', 'face', 'neck', 'weapon', 'trinket'])

# walk_ragged_array_of_length_prefixed_variable_length_structures
def w_ra_of_lpvls(
    header_struct_descriptor, data_struct_descriptor_template, footer_struct_descriptor,
    length_element_idx,
    blob, initial_offset, sequence_length,
    data_struct_processor=lambda h, d, f: d,
    collect_data=True
):
    data = []
    offset = initial_offset

    sizeof_header = struct.calcsize(header_struct_descriptor)
    if footer_struct_descriptor is not None:
        sizeof_footer = struct.calcsize(footer_struct_descriptor)
    else:
        sizeof_footer = 0

    for i in range(sequence_length):
        header = struct.unpack_from(header_struct_descriptor, blob, offset=offset)
        length_element = header[length_element_idx]
        offset += sizeof_header
        data_struct_descriptor = data_struct_descriptor_template.format(length=length_element)
        sizeof_data = struct.calcsize(data_struct_descriptor)
        if collect_data:
            data_element = struct.unpack_from(data_struct_descriptor, blob, offset=offset)
            if footer_struct_descriptor is not None:
                footer = struct.unpack_from(footer_struct_descriptor, blob, offset=offset + sizeof_data)
            else:
                footer = None
            data.append(data_struct_processor(header, data_element, footer))
        offset += sizeof_data
        offset += sizeof_footer
    return data, offset

def parse_string(blob, initial_offset, collect_data=True):
    offset = initial_offset
    length = struct.unpack_from('<Q', blob, offset=offset)[0]
    offset += 8
    if collect_data:
        s = struct.unpack_from(f'<{length}s', blob, offset=offset)[0].decode('utf-8')
    else:
        s = None
    offset += length
    return s, offset

class Cat:
    def __init__(self, sql_key, blob, verify_assumptions=True):
        self.sql_key = sql_key
        self.blob = blob

        # Pre-compute offsets past variable-length structures
        # messy... did not imagine that there'd be so many
        self.name_length_bytes = struct.unpack_from('<Q', self.blob, offset=12)[0] * 2
        self.name_offset_past = 20 + self.name_length_bytes
        self.nameplate_symbol_length_bytes = struct.unpack_from('<Q', self.blob, offset=self.name_offset_past)[0]
        self.nameplate_symbol_offset_past = self.name_offset_past + 8 + self.nameplate_symbol_length_bytes
        self.unknown_2_length_bytes = struct.unpack_from('<Q', self.blob, offset=self.nameplate_symbol_offset_past + 16)[0]
        self.unknown_2_offset_past = self.nameplate_symbol_offset_past + 24 + self.unknown_2_length_bytes
        self.voice_length_bytes = struct.unpack_from('<Q', self.blob, offset=self.unknown_2_offset_past + 368)[0]
        self.voice_offset_past = self.unknown_2_offset_past + 376 + self.voice_length_bytes
        _, self.last_injury_debuffed_stat_offset_past = parse_string(self.blob, self.voice_offset_past + 92, collect_data=False)
        self.campaign_stats_inner_offset_past = self.campaign_stats(calculate_offset=True)
        _, self.actives_basic_offset_past = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, self.campaign_stats_inner_offset_past, 2, collect_data=False)
        _, self.actives_accessible_offset_past = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, self.actives_basic_offset_past, 4, collect_data=False)
        _, self.actives_inherited_offset_past = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, self.actives_accessible_offset_past, 4, collect_data=False)
        _, self.passives_offset_past = w_ra_of_lpvls('<Q', '<{length}s', '<i', 0, self.blob, self.actives_inherited_offset_past, 2, collect_data=False)
        _, self.mutations_offset_past = w_ra_of_lpvls('<Q', '<{length}s', '<i', 0, self.blob, self.passives_offset_past, 2, collect_data=False)
        self.equipment_offset_past = self.equipment(calculate_offset=True)
        _, self.collar_offset_past = parse_string(self.blob, self.equipment_offset_past, collect_data=False)
        _, self.unknown_17_offset_past = w_ra_of_lpvls('<Q', '<{length}b', None, 0, self.blob, self.collar_offset_past + 28, 1, collect_data=False)
        # always verify full decode
        assert(self.unknown_17_offset_past + 79 == len(blob))

        self.verify_assumptions()

    def version(self):
        offset = 0
        return struct.unpack_from('<I', self.blob, offset=offset)[0]

    def entropy(self):
        offset = 4
        return struct.unpack_from('<Q', self.blob, offset=offset)[0]

    def name(self):
        offset = 20
        name_bytes = struct.unpack_from(f'<{self.name_length_bytes}s', self.blob, offset=offset)[0]
        return name_bytes.decode('utf-16')

    def nameplate_symbol(self):
        offset = self.name_offset_past + 8
        name_bytes = struct.unpack_from(f'<{self.nameplate_symbol_length_bytes}s', self.blob, offset=offset)[0]
        return name_bytes.decode('utf-8')

    def sex(self, raw_view=False):
        offset = self.nameplate_symbol_offset_past
        sex_bytes = struct.unpack_from(f'<i', self.blob, offset=offset)[0]
        if raw_view:
            return sex_bytes
        else:
            return ['male', 'female', 'neutral'][sex_bytes]

    def sex_dup(self, raw_view=False):
        offset = self.nameplate_symbol_offset_past + 4
        sex_bytes = struct.unpack_from(f'<i', self.blob, offset=offset)[0]
        if raw_view:
            return sex_bytes
        else:
            return ['male', 'female', 'neutral'][sex_bytes]

    def status_flags(self):
        offset = self.nameplate_symbol_offset_past + 8
        return struct.unpack_from(f'<Q', self.blob, offset=offset)[0]

    def unknown_2(self):
        offset = self.nameplate_symbol_offset_past + 24
        str_bytes = struct.unpack_from(f'<{self.unknown_2_length_bytes}s', self.blob, offset=offset)[0]
        return str_bytes.decode('utf-8')

    def unknown_3(self):
        offset = self.unknown_2_offset_past
        return struct.unpack_from(f'<i', self.blob, offset=offset)[0]

    def libido(self):
        offset = self.unknown_2_offset_past + 4
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def sexuality(self):
        offset = self.unknown_2_offset_past + 12
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def lover_sql_key(self):
        offset = self.unknown_2_offset_past + 20
        return struct.unpack_from(f'<q', self.blob, offset=offset)[0]

    def unknown_7(self):
        offset = self.unknown_2_offset_past + 28
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def aggression(self):
        offset = self.unknown_2_offset_past + 36
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def hater_sql_key(self):
        offset = self.unknown_2_offset_past + 44
        return struct.unpack_from(f'<q', self.blob, offset=offset)[0]

    def unknown_9(self):
        offset = self.unknown_2_offset_past + 52
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def unknown_10(self):
        offset = self.unknown_2_offset_past + 60
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def body_parts(self):
        offset = self.unknown_2_offset_past + 68
        texture_sprite_idx, heritable_palette_idx, collar_palette_idx = struct.unpack_from(f'<iii', self.blob, offset=offset)

        offset += 12
        limbs = []
        for i in range(14):
            limbs.append(BodyPartDescriptor._make(struct.unpack_from(f'<5i', self.blob, offset=offset)))

        offset += 14 * 5 * 4
        unknown_0, unknown_1 = struct.unpack_from(f'<ii', self.blob, offset=offset)

        offset += 8 + 8
        # assert(offset == self.unknown_2_offset_past + 376)
        voice = struct.unpack_from(f'<{self.voice_length_bytes}s', self.blob, offset=offset)[0].decode('utf-8')

        offset += self.voice_length_bytes
        # assert(offset == self.voice_offset_past)
        pitch = struct.unpack_from(f'<d', self.blob, offset=offset)[0]

        return BodyParts(texture_sprite_idx, heritable_palette_idx, collar_palette_idx, *limbs, unknown_0, unknown_1, voice, pitch)

    def stats_heritable(self):
        offset = self.voice_offset_past + 8
        return CatStats._make(struct.unpack_from(f'<7i', self.blob, offset=offset))

    def stats_delta_levelling(self):
        offset = self.voice_offset_past + 8 + 28
        return CatStats._make(struct.unpack_from(f'<7i', self.blob, offset=offset))

    def stats_delta_injuries(self):
        offset = self.voice_offset_past + 8 + 56
        return CatStats._make(struct.unpack_from(f'<7i', self.blob, offset=offset))

    def last_injury_debuffed_stat(self):
        offset = self.voice_offset_past + 92
        return parse_string(self.blob, offset)[0]

    def campaign_stats(self, calculate_offset=False):
        offset = self.last_injury_debuffed_stat_offset_past
        unknown_0, alive, unknown_1, unknown_2, array_size = struct.unpack_from(f'<i??iI', self.blob, offset=offset)

        offset += 14
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', '<i', 0, self.blob, offset, array_size, data_struct_processor=lambda h, d, f: (d[0].decode('utf-8'), f[0]), collect_data=not calculate_offset)

        if calculate_offset:
            return offset
        else:
            return CampaignStats(unknown_0, alive, unknown_1, unknown_2, array)

    def actives_basic(self):
        offset = self.campaign_stats_inner_offset_past
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, offset, 2, data_struct_processor=lambda h, d, f: d[0].decode('utf-8'))
        return array

    def actives_accessible(self):
        offset = self.actives_basic_offset_past
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, offset, 4, data_struct_processor=lambda h, d, f: d[0].decode('utf-8'))
        return array

    def actives_inherited(self):
        offset = self.actives_accessible_offset_past
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', None, 0, self.blob, offset, 4, data_struct_processor=lambda h, d, f: d[0].decode('utf-8'))
        return array

    def passives(self):
        offset = self.actives_inherited_offset_past
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', '<i', 0, self.blob, offset, 2, data_struct_processor=lambda h, d, f: (d[0].decode('utf-8'), f[0]))
        return array

    def mutations(self):
        offset = self.passives_offset_past
        array, offset = w_ra_of_lpvls('<Q', '<{length}s', '<i', 0, self.blob, offset, 2, data_struct_processor=lambda h, d, f: (d[0].decode('utf-8'), f[0]))
        return array

    def _equipment_helper(self, offset, calculate_offset=False):
        version, has_equipment = struct.unpack_from(f'<I?', self.blob, offset=offset)

        offset += 5
        if has_equipment:
            name, offset = parse_string(self.blob, offset, collect_data=not calculate_offset)
            unknown_0, offset = parse_string(self.blob, offset, collect_data=not calculate_offset)
            if calculate_offset:
                offset += 18
                return None, offset
            else:
                unknowns_1_6 = struct.unpack_from(f'<iiiibb', self.blob, offset=offset)
                offset += 18
                return Equipment(version, has_equipment, name, unknown_0, *unknowns_1_6), offset
        else:
            if calculate_offset:
                return None, offset
            else:
                return Equipment(version, has_equipment, None, None, None, None, None, None, None, None), offset

    def equipment(self, calculate_offset=False):
        offset = self.mutations_offset_past
        head, offset = self._equipment_helper(offset, calculate_offset=calculate_offset)
        face, offset = self._equipment_helper(offset, calculate_offset=calculate_offset)
        neck, offset = self._equipment_helper(offset, calculate_offset=calculate_offset)
        weapon, offset = self._equipment_helper(offset, calculate_offset=calculate_offset)
        trinket, offset = self._equipment_helper(offset, calculate_offset=calculate_offset)
        if calculate_offset:
            return offset
        else:
            return Kit(head, face, neck, weapon, trinket)

    def collar(self):
        offset = self.equipment_offset_past
        return parse_string(self.blob, offset)[0]

    def level(self):
        offset = self.collar_offset_past
        return struct.unpack_from(f'<i', self.blob, offset=offset)[0]

    def coi(self):
        offset = self.collar_offset_past + 4
        return struct.unpack_from(f'<d', self.blob, offset=offset)[0]

    def birthday(self):
        offset = self.collar_offset_past + 12
        return struct.unpack_from(f'<q', self.blob, offset=offset)[0]

    def deathday_house(self):
        offset = self.collar_offset_past + 20
        return struct.unpack_from(f'<q', self.blob, offset=offset)[0]

    def unknown_17(self):
        offset = self.collar_offset_past + 28
        return w_ra_of_lpvls('<Q', '<{length}b', None, 0, self.blob, self.collar_offset_past + 28, 1)[0]

    def unknown_19(self):
        offset = self.unknown_17_offset_past
        return struct.unpack_from(f'<I', self.blob, offset=offset)[0]

    def unknown_20(self):
        offset = self.unknown_17_offset_past + 4
        return struct.unpack_from(f'<Q', self.blob, offset=offset)[0]

    def unknown_21(self):
        offset = self.unknown_17_offset_past + 12
        return struct.unpack_from(f'<B', self.blob, offset=offset)[0]

    def unknown_22(self):
        offset = self.unknown_17_offset_past + 13
        return struct.unpack_from(f'<B', self.blob, offset=offset)[0]

    def unknown_23(self):
        offset = self.unknown_17_offset_past + 14
        return struct.unpack_from(f'<B', self.blob, offset=offset)[0]

    def injuries(self):
        offset = self.unknown_17_offset_past + 15
        return Injuries._make(struct.unpack_from(f'<16I', self.blob, offset=offset))

    def as_dict(self):
        return {
            'version': self.version(),
            'entropy': self.entropy(),
            'name': self.name(),
            'nameplate_symbol': self.nameplate_symbol(),
            'sex': self.sex(),
            'sex_dup': self.sex_dup(),
            'status_flags': self.status_flags(),
            'unknown_2': self.unknown_2(),
            'unknown_3': self.unknown_3(),
            'libido': self.libido(),
            'sexuality': self.sexuality(),
            'lover_sql_key': self.lover_sql_key(),
            'unknown_7': self.unknown_7(),
            'aggression': self.aggression(),
            'hater_sql_key': self.hater_sql_key(),
            'unknown_9': self.unknown_9(),
            'unknown_10': self.unknown_10(),
            'body_parts': self.body_parts(),
            'stats_heritable': self.stats_heritable(),
            'stats_delta_levelling': self.stats_delta_levelling(),
            'stats_delta_injuries': self.stats_delta_injuries(),
            'last_injury_debuffed_stat': self.last_injury_debuffed_stat(),
            'campaign_stats': self.campaign_stats(),
            'actives_basic': self.actives_basic(),
            'actives_accessible': self.actives_accessible(),
            'actives_inherited': self.actives_inherited(),
            'passives': self.passives(),
            'mutations': self.mutations(),
            'equipment': self.equipment(),
            'collar': self.collar(),
            'level': self.level(),
            'coi': self.coi(),
            'birthday': self.birthday(),
            'deathday_house': self.deathday_house(),
            'unknown_17': self.unknown_17(),
            'unknown_19': self.unknown_19(),
            'unknown_20': self.unknown_20(),
            'unknown_21': self.unknown_21(),
            'unknown_22': self.unknown_22(),
            'unknown_23': self.unknown_23(),
            'injuries': self.injuries(),
        }

    def verify_assumptions(self):
        try:
            self.assumptions()
        except:
            # with open('bad_kitty.bin', 'wb') as f:
            #     f.write(self.blob)
            raise Exception

    def assumptions(self):
        # Assert that we're working with a known version
        assert(self.version() == 19)

        # Does sex ever differ from sex_dup?
        assert(self.sex() == self.sex_dup())

        # TODO coverage collector on status_flags

        # Do unknown_2 and unknown_3 always carry a value of ('None', 1)?
        assert(self.unknown_2() == 'None')
        assert(self.unknown_3() == 1)

        # Does lover_sql_key == -1 => unknown_7 == 0.0?
        assert(implies(self.lover_sql_key() == -1, self.unknown_7() == 0.0))
        # may not be true depending on implementation, but assert anyway
        assert(cimplies(self.lover_sql_key() == -1, self.unknown_7() == 0.0))

        # Does hater_sql_key == -1 => unknown_9 == 0.0?
        assert(implies(self.hater_sql_key() == -1, self.unknown_9() == 0.0))
        # may not be true depending on implementation, but assert anyway
        assert(cimplies(self.hater_sql_key() == -1, self.unknown_9() == 0.0))

        # Can these fields ever outside [3, 7]?
        for stat in self.stats_heritable():
            assert(stat >= 3 and stat <= 7)

        # Can these fields ever be negative?
        # yes, events modify this field too
        #for stat in self.stats_delta_levelling():
            # assert(stat >= 0)

        # Can these fields ever be positive?
        for stat in self.stats_delta_injuries():
            assert(stat <= 0)

        # Are there any cats who were born before day -2?
        # (starter cats should be born on day -2, day 1 strays should be born on day -1)
        if self.birthday() < -2:
            assert(False)

        # Iff flags_dead and campaign_dead?
        flags_dead = bool((self.status_flags() >> 5) & 1)
        campaign_dead = self.campaign_stats().dead
        if flags_dead != campaign_dead:
            assert(False)

        # If deathday_house is not -1, is the cat dead?
        if not implies(self.deathday_house() != -1, flags_dead or campaign_dead):
            assert(False)

        # If the cat is dead, is deathday_house not -1
        # No, deathday_house appears to be written only if the cat died in the house,
        # probably so that the game can automatically remove its corpse in several days
        # if not cimplies(self.deathday_house() != -1, flags_dead or campaign_dead):
        #     print(self.sql_key, flags_dead, campaign_dead, self.deathday_house())
        #     assert(False)

        # Do injury counts correspond to stats_delta_injuries?
        # (note the debuff amounts are specified in injuries.gon)
        expected_debuffs = [
            # ['str', 'dex', 'con', 'int', 'spd', 'cha', 'lck']
            [-1, 0, 0, 0, 0, 0, 0], # broken_paw str
            [0, -1, 0, 0, 0, 0, 0], # torn_tendon dex
            [0, 0, -1, 0, 0, 0, 0], # broken_rib con
            [0, 0, 0, -1, 0, 0, 0], # concussion int
            [0, 0, 0, 0, 0, -1, 0], # disfigured cha
            [0, 0, 0, 0, -1, 0, 0], # broken_leg spd
            [0, 0, 0, 0, 0, 0, -1], # jinxed lck
            [0, 0, 0, 0, 0, -1, -1], # immolated cha lck
            [-1, -1, 0, 0, 0, 0, 0], # exsanguinated str dex
            [0, 0, -1, -1, 0, 0, 0], # poisoned con int
            [0, 0, 0, 0, 0, 0, -2], # cursed lck lck
            [0, 0, -1, 0, 0, 0, 0], # radiated con
            [0, 0, 0, 0, 0, 0, 0], # unused
            [0, 0, 0, 0, 0, 0, 0], # unused
            [0, 0, 0, 0, 0, 0, 0], # unused
            [0, 0, 0, 0, 0, 0, 0], # unused
        ]
        for stat_idx, stat_debuff_amt in enumerate(self.stats_delta_injuries()):
            predicted_debuff_amt = 0
            for injury_idx, injury_cnt in enumerate(self.injuries()):
                predicted_debuff_amt += expected_debuffs[injury_idx][stat_idx] * injury_cnt
            if stat_debuff_amt != predicted_debuff_amt:
                print(self.stats_delta_injuries())
                print(self.injuries())
                print(stat_idx, stat_debuff_amt, predicted_debuff_amt)
                assert(False)


def implies(a, b):
    # a => b
    return not a or b

def cimplies(a, b):
    # a <= b
    return not b or a

ParallelHashMapDump = namedtuple('ParallelHashMapDump', ['s_version', 'size', 'capacity', 'hash_table', 'data_table', 'growth_left'])
def scrape_hash_table(buffer, offset, unpack_string, unpack_size, raw_view=False):
    # in older versions of parallel-hashmap, the version field is not present
    # s_version < 2^64-1-10 are decoded as size and subsequent reads are frame-shifted by 1 qword
    # however, presumably, mewgenics never used those older library versions
    s_version, size, capacity = struct.unpack_from('<QQQ', buffer, offset=offset)

    # hash table contains capacity # of hash entries and 1 end of table marker
    # followed by a replicate of the first 16 hash entries
    hash_table_size = capacity + 1 + 16

    # we retrieve the non-EOT hash entries
    hash_table = struct.unpack_from(f'<{capacity}B', buffer, offset=offset + 24)

    # the hashing algorithm digests keys into a range 0x00-0x7F
    # and uses control values outside the range to represent an unoccupied bucket
    # these facts are sufficient to correctly scrape occupied data rows without fully reversing the digest implementation
    data_table = []
    for i in range(capacity):
        if raw_view or hash_table[i] <= 0x7f:
            data_table.append(struct.unpack_from(unpack_string, buffer, offset=offset + 24 + hash_table_size + i * unpack_size))

    # in older versions of parallel-hashmap, growth left is not present
    # presumably, mewgenics has always used versions where growth left is present
    growth_left = struct.unpack_from('<Q', buffer, offset=offset + 24 + hash_table_size + capacity * unpack_size)[0]

    start_of_next_table = offset + 24 + hash_table_size + capacity * unpack_size + 8

    if raw_view:
        return ParallelHashMapDump(s_version, size, capacity, hash_table, data_table, growth_left), start_of_next_table
    else:
        return data_table, start_of_next_table

class DumpedSaveReader:
    def __init__(self, directory):
        self.directory = directory

    def read_cats(self):
        cats = {}
        for cat_file in Path(self.directory, 'cats').iterdir():
            key = int(cat_file.stem)
            value = cat_file.read_bytes()
            cats[key] = Cat(key, value)
        return cats

    def read_pedigree(self, raw_view=False):
        result = Path(self.directory, 'files', 'pedigree.bin').read_bytes()

        start_of_next_table = 0
        pedigree_data, start_of_next_table = scrape_hash_table(result, start_of_next_table, '<qqqd', 32, raw_view=raw_view)
        coi_memo_table, start_of_next_table = scrape_hash_table(result, start_of_next_table, '<qqd', 24, raw_view=raw_view)
        accessible_cats_table, start_of_next_table = scrape_hash_table(result, start_of_next_table, '<q', 8, raw_view=raw_view)

        if raw_view:
            return pedigree_data, coi_memo_table, accessible_cats_table
        else:
            pedigree_dict = {x[0]: CatPedigree._make(x) for x in pedigree_data}
            coi_memo_dict = {x[0]: CatCoiMemo._make(x) for x in coi_memo_table}
            accessible_cats_set = set([x[0] for x in accessible_cats_table])
            return pedigree_dict, coi_memo_dict, accessible_cats_set
