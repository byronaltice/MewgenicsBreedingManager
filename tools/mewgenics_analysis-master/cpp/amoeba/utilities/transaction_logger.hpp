#pragma once

#include <fstream>
#include <filesystem>
#include <chrono>

#include "lz4frame.h"

// A binary logger for muxing separate data streams into a single file.
//
// polymeric 2026

// version independent header
// "AMOEBA"
// byte: version

// version 0 file
// byte: format: 0 - uncompressed, 1 - framed lz4, others - reserved
// <start of compressed zone>
// record...
// <end of compressed zone>

// records can be classified as full or compact by checking the first byte of the record

// version 0 full record
// byte: c-type (0)
// 3-word: s-type
// 4-byte*: user (length-independent data)
// qword: length
// payload (length-dependent data)

// *serializers/deserializers may treat this field as dword. users must pack/unpack bytes as required

// version 0 compact record
// byte: c-type (1-255)
// payload

// version 0 full type encodings (s-type for sub-type)
// 0: binary blob
// 1-255: aliases to compact type encodings
// 256: utf-8 string

// version 0 compact type encodings (c-type for compact-type)
// data types
// 0: full record
// 1: not available
// 2: int64
// 3: double
// control types
// 253(-3): set timestamp (signed microseconds since Unix epoch)
// 254(-2): select virtual stream
// 255(-1): end of physical stream; reset all virtual stream state

enum class CompactRecordCTypes : uint8_t {
    FullRecord = 0,
    NA = 1,
    Int64 = 2,
    Double = 3,
    SetTimestamp = 253,
    SelectVsid = 254,
    Reset = 255,
};

enum class FullRecordSTypes : uint32_t {
    Blob = 0,
    // 1-255 decode to a CompactRecordType
    StringUtf8 = 256,
};

class TransactionLogger {
public:
    TransactionLogger(std::filesystem::path file_path, bool use_lz4);
    ~TransactionLogger();

    void open();
    void close();

    void reset(bool write_full = false);
    void select_vsid(uint32_t vsid, bool write_full = false);
    void set_timestamp(int64_t timestamp_us_unix_epoch, bool write_full=false);
    void set_timestamp(std::chrono::time_point<std::chrono::system_clock> timestamp, bool write_full=false);
    void set_timestamp_now(bool write_full=false);

    void write_na(bool write_full=false);
    void write_int64(int64_t val, bool write_full=false);
    void write_double(double val, bool write_full=false);
    void write_blob_from_file(std::string file_path_to_copy);
    void write_blob(const void *ptr, uint64_t size, uint32_t user=0);
    void write_string(std::string string, uint32_t user=0);

private:
    const size_t CHUNK_SIZE = 64 * 1024;
    std::filesystem::path file_path;
    std::ofstream file;
    uint8_t format;
    std::vector<char> stream_buffer;
    std::vector<char> compress_buffer;
    LZ4F_cctx *lz4_cctx;
    LZ4F_preferences_t lz4_preferences;

    void write_header();
    void write_footer();

    void write_wrapped(const char* ptr, uint64_t size);
    void write_wrapped_ifstream(std::ifstream& ifstream, uint64_t size);

    constexpr uint32_t type_from_stype(FullRecordSTypes stype);

    // user can be any 4-byte data type (e.g. char[4]); uint32_t is used as a dummy 4-byte type for argument passing
    void write_full_record(uint32_t type, std::ifstream& ifstream, uint64_t size, uint32_t user=0);
    void write_full_record(uint32_t type, const void* ptr, uint64_t size, uint32_t user=0);
    void write_compact_record(uint8_t ctype, const void* ptr, uint64_t size, bool write_full=false, uint32_t user=0);
};
