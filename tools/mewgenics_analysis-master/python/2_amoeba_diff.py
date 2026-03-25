from common.dumped_save import Cat
from common.sql_save import SqlSaveTmpReader

from collections import namedtuple
from enum import Enum
import struct
import lz4.frame
from datetime import datetime
import collections.abc
import base64

'''
Reads an Amoeba transaction log file written by amoeba.dll,
parses structures from its sql(2) and savefile(3) channels,
and reports what actually changed.

See cpp/amoeba for the source to amoeba.dll.

polymeric 2026
'''

AMOEBA_TLOG_PATH = '../in/zaratana.tlog.lz4'

AmoebaControl = namedtuple('AmoebaControl', ['kind', 'x'])

class MetaInterpreterState(Enum):
    READY = 0
    HALT = 1

class MetaInterpreter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = MetaInterpreterState.READY
        self.schema = 0

    def message(self, value):
        if self.state == MetaInterpreterState.READY:
            if type(value) is int:
                self.schema = value
                self.state = MetaInterpreterState.HALT
        elif self.state == MetaInterpreterState.HALT:
            return None

class LogInterpreterState(Enum):
    READY = 0
    HALT = 1

class LogInterpreter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = LogInterpreterState.READY

    def message(self, user, value):
        if self.state == LogInterpreterState.READY:
            if type(value) is str:
                user_level = int(user[0])
                return user_level, value
        elif self.state == LogInterpreterState.HALT:
            return None

class SqlStreamInterpreterState(Enum):
    READY = 0
    HALT = 1
    AWAIT_FILENAME = 2
    AWAIT_SIZE = 3
    AWAIT_QUERY_STRING = 4
    AWAIT_KEY = 5
    AWAIT_VAL = 6

class SqlStreamInterpreter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = SqlStreamInterpreterState.READY
        self.buf_filename = None
        self.buf_params_count = 0
        self.buf_query_string = ''
        self.buf_key = ''
        self.buf_val = ''
        self.buf_params = {}

    def message(self, value, schema):
        epsilon_jump = True
        while epsilon_jump:
            epsilon_jump = False
            if self.state == SqlStreamInterpreterState.READY:
                epsilon_jump = True
                self.state = SqlStreamInterpreterState.AWAIT_FILENAME
            elif self.state == SqlStreamInterpreterState.HALT:
                return None
            elif self.state == SqlStreamInterpreterState.AWAIT_FILENAME:
                if schema <= 0:
                    self.buf_filename = None
                    epsilon_jump = True
                    self.state = SqlStreamInterpreterState.AWAIT_SIZE
                else:
                    if type(value) is str:
                        self.buf_filename = value
                        self.state = SqlStreamInterpreterState.AWAIT_SIZE
                    else:
                        self.state = SqlStreamInterpreterState.HALT
            elif self.state == SqlStreamInterpreterState.AWAIT_SIZE:
                if type(value) is int:
                    self.buf_params_count = value
                    self.buf_params = {}
                    self.state = SqlStreamInterpreterState.AWAIT_QUERY_STRING
                else:
                    self.state = SqlStreamInterpreterState.HALT
            elif self.state == SqlStreamInterpreterState.AWAIT_QUERY_STRING:
                if type(value) is str:
                    self.buf_query_string = value
                    if self.buf_params_count > 0:
                        self.state = SqlStreamInterpreterState.AWAIT_KEY
                    else:
                        self.state = SqlStreamInterpreterState.READY
                else:
                    self.state = SqlStreamInterpreterState.HALT
            elif self.state == SqlStreamInterpreterState.AWAIT_KEY:
                if type(value) is str:
                    self.buf_key = value
                    self.state = SqlStreamInterpreterState.AWAIT_VAL
                else:
                    self.state = SqlStreamInterpreterState.HALT
            elif self.state == SqlStreamInterpreterState.AWAIT_VAL:
                self.buf_params[self.buf_key] = value
                self.buf_params_count -= 1
                if self.buf_params_count > 0:
                    self.state = SqlStreamInterpreterState.AWAIT_KEY
                else:
                    self.state = SqlStreamInterpreterState.READY
            else:
                raise Exception

        if self.state == SqlStreamInterpreterState.READY:
            response = (self.buf_filename, self.buf_query_string, self.buf_params)
            assert(self.buf_params_count == 0)
            return response

class SavefileStreamInterpreterState(Enum):
    READY = 0
    HALT = 1
    AWAIT_FILENAME = 2
    AWAIT_BLOB = 3

class SavefileStreamInterpreter:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = SavefileStreamInterpreterState.READY
        self.buf_modified = 0
        self.buf_filename = ''
        self.buf_blob = ''

    def message(self, value):
        if self.state == SavefileStreamInterpreterState.READY:
            if type(value) is int:
                self.buf_modified = value
                self.state = SavefileStreamInterpreterState.AWAIT_FILENAME
            else:
                self.state = SavefileStreamInterpreterState.HALT
        elif self.state == SavefileStreamInterpreterState.HALT:
            return None
        elif self.state == SavefileStreamInterpreterState.AWAIT_FILENAME:
            if type(value) is str:
                self.buf_filename = value
                self.state = SavefileStreamInterpreterState.AWAIT_BLOB
            else:
                self.state = SavefileStreamInterpreterState.HALT
        elif self.state == SavefileStreamInterpreterState.AWAIT_BLOB:
            if type(value) is bytes:
                self.buf_blob = value
                self.state = SavefileStreamInterpreterState.READY
            else:
                self.state = SavefileStreamInterpreterState.HALT
        else:
            raise Exception

        if self.state == SavefileStreamInterpreterState.READY:
            response = (self.buf_modified, self.buf_filename, self.buf_blob)
            self.buf_blob = ''
            return response

def compare_dicts(left, right):
    left_keys = set(left.keys())
    right_keys = set(right.keys())

    left_only = left_keys - right_keys
    right_only = right_keys - left_keys

    intersection = left_keys.intersection(right_keys)

    differences = {k for k in intersection if left[k] != right[k]}
    return left_only, differences, right_only

def repr_val(x):
    # namedtuple handling
    if hasattr(x, '_asdict'):
        return x._asdict()
    # byte arrays
    elif isinstance(x, bytes):
        return base64.b64encode(x).decode('ascii')
    else:
        return x

def recursive_x_report(x, lval, rval, thing, indent=0, prefix=''):
    lval = repr_val(lval)
    rval = repr_val(rval)
    if isinstance(lval, collections.abc.Sequence) and isinstance(rval, collections.abc.Sequence) and len(lval) == len(rval) and not isinstance(lval, str):
        # print(' ' * indent, end='')
        # print(f'{thing} {x} changed')
        for i,(lvv, rvv) in enumerate(zip(lval, rval)):
            if lvv != rvv:
                # print(' ' * indent, end='')
                # print(f'{thing} {prefix}{x}[{i}] changed')
                recursive_x_report(i, lvv, rvv, 'field', indent=indent, prefix=f'{prefix}[{i}]')
    elif isinstance(lval, collections.abc.Mapping) and isinstance(rval, collections.abc.Mapping):
        # print(' ' * indent, end='')
        # print(f'{thing} {x} changed')
        lkeys = set(lval.keys())
        rkeys = set(rval.keys())
        if lkeys == rkeys:
            for k in lkeys:
                lvv = lval[k]
                rvv = rval[k]
                if lvv != rvv:
                    # print(' ' * indent, end='')
                    # print(f'{thing} {prefix}{x}[{k}] changed')
                    recursive_x_report(k, lvv, rvv, 'field', indent=indent, prefix=f'{prefix}[{k}]')
    else:
        print(' ' * indent, end='')
        print(f'UPDATE {thing} {prefix} ({lval} -> {rval})')

def ldr_report(l, d, r, thing, ldict, rdict, style='short', indent=0):
    for x in l:
        print(' ' * indent, end='')
        if style == 'val':
            lval = repr_val(ldict[x])
            print(f'DELETE {thing} {x} ({lval})')
        else:
            print(f'DELETE {thing} {x}')
    for x in d:
        if style == 'val':
            lval = repr_val(ldict[x])
            rval = repr_val(rdict[x])
            recursive_x_report(x, lval, rval, thing, indent=indent, prefix=f'{x}')
        elif style == 'cat':
            print(' ' * indent, end='')
            lcat = Cat(x, ldict[x]).as_dict()
            rcat = Cat(x, rdict[x]).as_dict()
            print(f'UPDATE {thing} {x}')
            ldr_report(*compare_dicts(lcat, rcat), 'field', lcat, rcat, style='val', indent=4)
        else:
            print(' ' * indent, end='')
            print(f'UPDATE {thing} {x}')
    for x in r:
        print(' ' * indent, end='')
        if style == 'val':
            rval = repr_val(rdict[x])
            print(f'INSERT {thing} {x} ({rval})')
        else:
            print(f'INSERT {thing} {x}')


class SavefileStateDiffer:
    def __init__(self):
        self.loaded = False
        self.filepath = ''
        self.cats = {}
        self.furniture = {}
        self.files = {}
        self.properties = {}

    def message_sql(self, sql_data):
        pass

    def message_savedata(self, save_data, schema):
        modified = save_data[0]
        filepath = save_data[1]
        blob = save_data[2]

        # if filepath == 'test00.sav':
        #     return

        if schema == 1:
            modified_time = datetime.fromtimestamp(modified / 1000000.0)
        else:
            modified_time = datetime.fromtimestamp(modified / 1000000.0 - 11644473600.0)

        with SqlSaveTmpReader(blob) as db:
            cats = db.read_cats()
            furniture = db.read_furniture()
            files = db.read_files()
            properties = db.read_properties()

        if self.loaded and filepath == self.filepath:
            print(f'Save on {modified_time}')
            ldr_report(*compare_dicts(self.cats, cats), 'cat', self.cats, cats, style='cat')
            ldr_report(*compare_dicts(self.furniture, furniture), 'furniture', self.furniture, furniture)
            ldr_report(*compare_dicts(self.files, files), 'file', self.files, files)
            ldr_report(*compare_dicts(self.properties, properties), 'property', self.properties, properties, style='val')

        if filepath == self.filepath:
            self.cats = cats
            self.furniture = furniture
            self.files = files
            self.properties = properties

        if not self.loaded:
            self.loaded = True
            self.filepath = filepath

def read_compact(f, ctype):
    if ctype == 1:
        return None
    elif ctype == 2:
        return int.from_bytes(f.read(8), 'little', signed=False)
    elif ctype == 3:
        return struct.unpack('<d', f.read(8))[0]
    elif ctype == 253:
        return AmoebaControl('set_timestamp', int.from_bytes(f.read(8), 'little', signed=False))
    elif ctype == 254:
        return AmoebaControl('select_vsid', int.from_bytes(f.read(4), 'little', signed=False))
    elif ctype == 255:
        return AmoebaControl('reset', None)
    else:
        raise Exception(ctype)

def read_full(f, stype, length):
    if stype == 0:
        return f.read(length)
    elif stype > 0 and stype < 256:
        return read_compact(f, stype)
    elif stype == 256:
        return f.read(length).decode('utf-8')
    else:
        raise Exception(stype)

def main():
    ssd = SavefileStateDiffer()
    mti = MetaInterpreter()
    lti = LogInterpreter()
    ssi = SqlStreamInterpreter()
    svi = SavefileStreamInterpreter()
    with open(AMOEBA_TLOG_PATH, 'rb') as f:
        header = f.read(8)
        magic, version, fmt = struct.unpack('<6sbb', header)
        assert(magic == b'AMOEBA')
        assert(version == 0)
        assert(fmt == 1)

        with lz4.frame.open(f, 'rb') as f:
            current_vsid = 0
            while ctype := f.read(1):
                ctype = int.from_bytes(ctype, 'little', signed=False)
                if ctype == 0:
                    # full
                    stype = int.from_bytes(f.read(3), 'little', signed=False)
                    user = f.read(4)
                    length = int.from_bytes(f.read(8), 'little', signed=False)
                    rec = read_full(f, stype, length)
                else:
                    # compact
                    rec = read_compact(f, ctype)
                # print(rec)
                if type(rec) is AmoebaControl:
                    if rec.kind == 'select_vsid':
                        current_vsid = rec.x
                elif current_vsid == 0:
                    mti.message(rec)
                elif current_vsid == 1:
                    response = lti.message(user, rec)
                    # if response is not None:
                    #     print(response)
                elif current_vsid == 2:
                    response = ssi.message(rec, mti.schema)
                    if response:
                        if not response[1].startswith('SELECT'):
                            # print(response[0])
                            pass
                        # print(response)
                elif current_vsid == 3:
                    response = svi.message(rec)
                    if response:
                        ssd.message_savedata(response, mti.schema)
                        # print(f'wrote {response[1]}')
                        # print(response)

if __name__ == '__main__':
    main()
