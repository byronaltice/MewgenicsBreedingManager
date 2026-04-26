from pathlib import Path
import sqlite3
import lz4.block
import tempfile
import shutil

class SqlSaveReader:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()
        return False

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def cursor(self):
        return self.conn.cursor()

    def read_all_generic_kv(self, table_name, data_wrapper=lambda x: x):
        ret = {}
        cursor = self.cursor()
        cursor.execute(f'SELECT key, data FROM {table_name}')
        # typo, cat got my tongue >:3
        while reow := cursor.fetchone():
            key, data = reow
            ret[key] = data_wrapper(data)
        cursor.close()
        return ret

    def read_cats(self):
        return self.read_all_generic_kv('cats', data_wrapper=lz4.block.decompress)

    def read_furniture(self):
        return self.read_all_generic_kv('furniture')

    def read_files(self):
        return self.read_all_generic_kv('files')

    def read_properties(self):
        return self.read_all_generic_kv('properties')

# with Python 3.11+ we could use deserialize instead
class SqlSaveTmpReader(SqlSaveReader):
    def __init__(self, buf):
        self.tmpdir = tempfile.mkdtemp(prefix='mewgenics_analysis_sql_save_tmp')
        self.tmpfile = Path(self.tmpdir, 'temp.sav')
        with open(self.tmpfile, 'wb') as f:
            f.write(buf)
        super().__init__(self.tmpfile)

    def close(self):
        super().close()
        if self.tmpdir is not None:
            shutil.rmtree(self.tmpdir, ignore_errors=False)
            self.tmpdir = None
            self.tmpfile = None
