"""Check GON files for IDs 139 (eyes) and 23 (eyebrows) and scan Whommie's blob."""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')

import struct, re, lz4.block, sqlite3
from save_parser import parse_save, GameData, set_visual_mut_data, BinaryReader

SAVE = os.path.expandvars(r'%USERPROFILE%\gitprojects\MewgenicsBreedingManager\test-saves\steamcampaign01.sav')
GPAK = os.path.expandvars(r'%USERPROFILE%\gitprojects\MewgenicsBreedingManager\test-saves\resources.gpak')

gd = GameData.from_gpak(GPAK)
set_visual_mut_data(gd.visual_mutation_data)

# Read GON files and look for IDs 139 and 23
with open(GPAK, 'rb') as f:
    count = struct.unpack('<I', f.read(4))[0]
    entries = []
    for _ in range(count):
        nlen = struct.unpack('<H', f.read(2))[0]
        name = f.read(nlen).decode('utf-8', errors='replace')
        size = struct.unpack('<I', f.read(4))[0]
        entries.append((name, size))
    dir_end = f.tell()
    file_offsets = {}
    offset = dir_end
    for name, size in entries:
        file_offsets[name] = (offset, size)
        offset += size

    for fname, target_ids in [('data/mutations/eyes.gon', [139, 2]), ('data/mutations/eyebrows.gon', [23, 2])]:
        foff, fsz = file_offsets[fname]
        f.seek(foff)
        content = f.read(fsz).decode('utf-8', errors='replace')
        print(f"\n=== {fname}: IDs {target_ids} ===")
        for m in re.finditer(r'(?<!\w)(\d+)\s*\{', content):
            sid = int(m.group(1))
            if sid not in target_ids:
                continue
            start = m.end()
            depth, end = 1, start
            while end < len(content) and depth > 0:
                if content[end] == '{': depth += 1
                elif content[end] == '}': depth -= 1
                end += 1
            block = content[start:end-1]
            print(f"  ID {sid}: {block[:300]!r}")

# Scan Whommie's blob for defect-related values
save_data = parse_save(SAVE)
cats = save_data.cats
whommie = next(c for c in cats if c.name == "Whommie")

con = sqlite3.connect(f"file:{SAVE}?mode=ro", uri=True)
cat_blobs = {k: v for k, v in con.execute("SELECT key, data FROM cats").fetchall()}
con.close()

blob = cat_blobs[whommie.db_key]
uncomp = struct.unpack('<I', blob[:4])[0]
raw = lz4.block.decompress(blob[4:], uncompressed_size=uncomp)
r = BinaryReader(raw)
r.u32(); r.u64(); r.utf16str(); r.str(); r.u64(); r.u64(); r.str(); r.u32(); r.skip(64)
T_start = r.pos
T = [r.u32() for _ in range(72)]

SEARCH = {0xFFFF_FFFE, 0xFFFF_FFFF} | set(range(700, 712))
print(f"\nWhommie blob: searching for defect values outside T array (T is bytes {T_start}-{T_start+288})")
for i in range(0, len(raw) - 3):
    v = struct.unpack_from('<I', raw, i)[0]
    if v in SEARCH:
        in_T = T_start <= i < T_start + 288
        print(f"  offset {i}: {v} (0x{v:08X}) {'[in T]' if in_T else '[OUTSIDE T]'}")
