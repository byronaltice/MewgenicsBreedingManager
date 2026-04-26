import struct
import lz4.frame

'''
Reads an LZ4-compressed Amoeba transaction log file and decompresses it to another file.

polymeric 2026
'''

def main():
    with open('test.tlog.lz4', 'rb') as f:
        header = f.read(8)
        magic, version, fmt = struct.unpack('<6sbb', header)
        assert(magic == b'AMOEBA')
        assert(version == 0)
        assert(fmt == 1)

        decomp = lz4.frame.LZ4FrameDecompressor()

        with open('test.tlog', 'wb') as f2:
            f2.write(b'AMOEBA\0\0')
            while read_chunk := f.read(64*1024):
                f2.write(decomp.decompress(read_chunk, max_length=64*1024))
                while not decomp.needs_input:
                    f2.write(decomp.decompress(b'', max_length=64*1024))
        assert(decomp.eof)

if __name__ == '__main__':
    main()
