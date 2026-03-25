from common.sql_save import SqlSaveReader
from pathlib import Path
import os
import shutil
import json
import lz4.block
import base64

SAVE_FILE_PATH = '../in/steamcampaign01.sav'
SAVE_DUMP_PATH_PREFIX = '../out/dumped_save'

'''
Reads a Mewgenics save file and dumps its contents into individual files
for further analysis.

cats(INTEGER PRIMARY KEY key, BLOB data)
    LZ4-decompressed before dumping into files with names corresponding to 64-bit numeric key.
furniture(INTEGER PRIMARY KEY key, BLOB data)
    Dumped as-is into files with names corresponding to 64-bit numeric key.
files(TEXT NOT NULL PRIMARY KEY key, BLOB data)
    Dumped as-is into files with names corresponding to string key.
properties(TEXT NOT NULL PRIMARY KEY key, ANY data)
    Dumped in a single file as k-v pairs in a JSON object. BLOB values are base64-encoded and represented as JSON strings.
winning_teams(INTEGER PRIMARY KEY key, BLOB data)
    Appears to be unused, not dumped.

Mewgenics 1.0.20695

polymeric 2026
'''

def dump_cats(reader, directory):
    cursor = reader.cursor()
    cursor.execute('SELECT key, data FROM cats')
    # typo, cat got my tongue >:3
    while reow := cursor.fetchone():
        key, data = reow
        # ceil(lg(2^64-1)) == 20, so pad zeroes until 20 wide
        file_path = Path(directory, f'{key:020d}.bin')
        with open(file_path, 'wb') as f:
            # glaiel::ByteStream::Decompress_LZ4 prepends a length prefix
            # lz4.block assumes first 4 bytes are u32 decompressed length
            f.write(lz4.block.decompress(data))
    cursor.close()

def dump_furniture(reader, directory):
    cursor = reader.cursor()
    cursor.execute('SELECT key, data FROM furniture')
    while row := cursor.fetchone():
        key, data = row
        file_path = Path(directory, f'{key:020d}.bin')
        with open(file_path, 'wb') as f:
            f.write(data)
    cursor.close()

def dump_files(reader, directory):
    cursor = reader.cursor()
    cursor.execute('SELECT key, data FROM files')
    while row := cursor.fetchone():
        key, data = row
        file_path = Path(directory, f'{key}.bin')
        with open(file_path, 'wb') as f:
            f.write(data)
    cursor.close()

def dump_properties(reader, file_path):
    table = reader.read_properties()
    for k, v in table.items():
        # e.g. 'random_seed' is xoshiro256+ context
        if type(v) is bytes:
            table[k] = base64.b64encode(v).decode('ascii')
    with open(file_path, 'wt') as f:
        json.dump(table, f, indent=4)

def main():
    with SqlSaveReader(SAVE_FILE_PATH) as save_reader:
        shutil.rmtree(SAVE_DUMP_PATH_PREFIX, ignore_errors=True)

        cats_directory = Path(SAVE_DUMP_PATH_PREFIX, 'cats')
        os.makedirs(cats_directory, exist_ok=False)
        dump_cats(save_reader, cats_directory)

        furniture_directory = Path(SAVE_DUMP_PATH_PREFIX, 'furniture')
        os.makedirs(furniture_directory, exist_ok=False)
        dump_furniture(save_reader, furniture_directory)

        files_directory = Path(SAVE_DUMP_PATH_PREFIX, 'files')
        os.makedirs(files_directory, exist_ok=False)
        dump_files(save_reader, files_directory)

        properties_path = Path(SAVE_DUMP_PATH_PREFIX, 'properties.json')
        dump_properties(save_reader, properties_path)

if __name__ == '__main__':
    main()
