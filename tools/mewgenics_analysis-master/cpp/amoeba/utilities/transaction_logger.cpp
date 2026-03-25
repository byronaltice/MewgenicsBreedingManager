#include "transaction_logger.hpp"
#include "debug_console.hpp"

#include <algorithm>

#include "lz4frame.h"

// A binary logger for muxing separate data streams into a single file.
//
// polymeric 2026

TransactionLogger::TransactionLogger(std::filesystem::path file_path, bool use_lz4) {
    this->file_path = file_path;
    this->lz4_preferences = LZ4F_INIT_PREFERENCES;
    if(use_lz4) {
        this->format = 1;
    } else {
        this->format = 0;
    }
}

TransactionLogger::~TransactionLogger() {
    this->close();
}

void TransactionLogger::open() {
    if(!this->file.is_open()) {
        this->file = std::ofstream(this->file_path, std::ios::binary); // TODO can throw
        this->stream_buffer.resize(this->CHUNK_SIZE);
        if(this->format == 1) {
            LZ4F_createCompressionContext(&this->lz4_cctx, LZ4F_VERSION); // TODO can fail
            this->compress_buffer.resize((std::max)(static_cast<size_t>(LZ4F_HEADER_SIZE_MAX), LZ4F_compressBound(this->CHUNK_SIZE, &this->lz4_preferences)));
        }

        write_header();
    }
}

void TransactionLogger::close() {
    if(this->file.is_open()) {
        write_footer();

        if(this->format == 1) {
            this->compress_buffer.clear();
            // nullptr check is internal to the library function
            LZ4F_freeCompressionContext(this->lz4_cctx);
        }
        this->stream_buffer.clear();

        this->file.close();
    }
}

void TransactionLogger::reset(bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::Reset);
    this->write_compact_record(ctype, nullptr, 0, write_full);
}

void TransactionLogger::select_vsid(uint32_t vsid, bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::SelectVsid);
    this->write_compact_record(ctype, &vsid, 4, write_full, vsid);
}

void TransactionLogger::set_timestamp(int64_t timestamp_us_unix_epoch, bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::SetTimestamp);
    this->write_compact_record(ctype, &timestamp_us_unix_epoch, 8, write_full);
}

void TransactionLogger::set_timestamp(std::chrono::time_point<std::chrono::system_clock> timestamp, bool write_full) {
    set_timestamp(std::chrono::duration_cast<std::chrono::microseconds>(timestamp.time_since_epoch()).count(), write_full);
}

void TransactionLogger::set_timestamp_now(bool write_full) {
    set_timestamp(std::chrono::system_clock().now(), write_full);
}

void TransactionLogger::write_na(bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::NA);
    this->write_compact_record(ctype, nullptr, 0, write_full);
}

void TransactionLogger::write_int64(int64_t val, bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::Int64);
    this->write_compact_record(ctype, &val, 8, write_full);
}

void TransactionLogger::write_double(double val, bool write_full) {
    const uint32_t ctype = static_cast<uint8_t>(CompactRecordCTypes::Double);
    this->write_compact_record(ctype, &val, 8, write_full);
}

void TransactionLogger::write_blob_from_file(std::string file_path_to_copy) {
    uint64_t size = std::filesystem::file_size(file_path_to_copy);
    std::ifstream file_to_copy(file_path_to_copy, std::ios::binary);
    const uint32_t type = type_from_stype(FullRecordSTypes::Blob);
    this->write_full_record(type, file_to_copy, size);
}

void TransactionLogger::write_blob(const void *ptr, uint64_t size, uint32_t user) {
    const uint32_t type = type_from_stype(FullRecordSTypes::Blob);
    this->write_full_record(type, ptr, size, user);
}

void TransactionLogger::write_string(std::string string, uint32_t user) {
    const uint32_t type = type_from_stype(FullRecordSTypes::StringUtf8);
    this->write_full_record(type, string.data(), string.length(), user);
}

void TransactionLogger::write_header() {
    // 6 byte magic
    this->file.write("AMOEBA", 6);
    // version byte
    this->file.put(0);
    // format byte
    this->file.put(this->format);

    if(this->format == 1) {
        size_t written_size = LZ4F_compressBegin(this->lz4_cctx, this->compress_buffer.data(), this->compress_buffer.size(), &this->lz4_preferences);
        if(LZ4F_isError(written_size)) {
            // TODO somehow signal error
            D::error("lz4 - error - {}", LZ4F_getErrorName(written_size));
        }
        this->file.write(this->compress_buffer.data(), written_size);
    }
}

void TransactionLogger::write_footer() {
    if(this->format == 1) {
        size_t written_size = LZ4F_compressEnd(this->lz4_cctx, this->compress_buffer.data(), this->compress_buffer.size(), nullptr);
        if(LZ4F_isError(written_size)) {
            // TODO somehow signal error
            D::error("lz4 - error - {}", LZ4F_getErrorName(written_size));
        }
        this->file.write(this->compress_buffer.data(), written_size);
    }
}

void TransactionLogger::write_wrapped(const char* ptr, uint64_t size) {
    if(file.is_open()) {
        if(this->format == 1) {
            uint64_t remaining_size = size;
            uint64_t size_to_stream = CHUNK_SIZE;
            while(remaining_size > 0) {
                if(remaining_size < this->CHUNK_SIZE) {
                    size_to_stream = remaining_size;
                    remaining_size = 0;
                } else {
                    remaining_size -= CHUNK_SIZE;
                }
                size_t written_size = LZ4F_compressUpdate(this->lz4_cctx, this->compress_buffer.data(), this->compress_buffer.size(), ptr, size_to_stream, nullptr);
                ptr += size_to_stream;
                if(LZ4F_isError(written_size)) {
                    // TODO somehow signal error
                    D::error("lz4 - error - {}", LZ4F_getErrorName(written_size));
                }
                if(written_size > 0) {
                    this->file.write(this->compress_buffer.data(), written_size);
                }
            }
        } else {
            this->file.write(reinterpret_cast<const char*>(ptr), size);
        }
    }
}

void TransactionLogger::write_wrapped_ifstream(std::ifstream& ifstream, uint64_t size) {
    if(file.is_open()) {
        uint64_t remaining_size = size;
        uint64_t size_to_stream = CHUNK_SIZE;
        while(remaining_size > 0) {
            if(remaining_size < this->CHUNK_SIZE) {
                size_to_stream = remaining_size;
                remaining_size = 0;
            } else {
                remaining_size -= CHUNK_SIZE;
            }
            ifstream.read(stream_buffer.data(), size_to_stream);
            if(this->format == 1) {
                size_t written_size = LZ4F_compressUpdate(this->lz4_cctx, this->compress_buffer.data(), this->compress_buffer.size(), stream_buffer.data(), size_to_stream, nullptr);
                if(LZ4F_isError(written_size)) {
                    // TODO somehow signal error
                    D::error("lz4 - error - {}", LZ4F_getErrorName(written_size));
                }
                if(written_size > 0) {
                    this->file.write(this->compress_buffer.data(), written_size);
                }
            } else {
                this->file.write(stream_buffer.data(), size_to_stream);
            }
        }
    }
}

constexpr uint32_t TransactionLogger::type_from_stype(FullRecordSTypes stype) {
    return static_cast<uint32_t>(stype) << 8;
}

void TransactionLogger::write_full_record(uint32_t type, std::ifstream& ifstream, uint64_t size, uint32_t user) {
    this->write_wrapped(reinterpret_cast<const char*>(&type), 4);
    this->write_wrapped(reinterpret_cast<const char*>(&user), 4);
    this->write_wrapped(reinterpret_cast<const char*>(&size), 8);
    this->write_wrapped_ifstream(ifstream, size);
}

void TransactionLogger::write_full_record(uint32_t type, const void* ptr, uint64_t size, uint32_t user) {
    this->write_wrapped(reinterpret_cast<const char*>(&type), 4);
    this->write_wrapped(reinterpret_cast<const char*>(&user), 4);
    this->write_wrapped(reinterpret_cast<const char*>(&size), 8);
    this->write_wrapped(static_cast<const char*>(ptr), size);
}

void TransactionLogger::write_compact_record(uint8_t ctype, const void* ptr, uint64_t size, bool write_full, uint32_t user) {
    if(write_full) {
        uint32_t type = static_cast<uint32_t>(ctype) << 8;
        write_full_record(type, ptr, size, user);
    } else {
        this->write_wrapped(reinterpret_cast<const char*>(&ctype), 1);
        this->write_wrapped(static_cast<const char*>(ptr), size);
    }
}
