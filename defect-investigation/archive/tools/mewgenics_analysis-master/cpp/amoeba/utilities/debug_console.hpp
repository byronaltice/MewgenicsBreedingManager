#pragma once

// Opens a console on the host process via AllocConsole and uses the host's stdout for writing debug prints
// #define SHOW_WIN32_CONSOLE

#include "transaction_logger.hpp"
#include "utilities/strings.hpp"

#include <cstdint>
#include <string>
#include <format>
#include <chrono>
#include <windows.h>

// Debug printing facilities.
//
// polymeric 2026

#ifdef SHOW_WIN32_CONSOLE
#define ALLOC_CONSOLE() AllocConsole()
#define FREE_CONSOLE() FreeConsole()
#else
#define ALLOC_CONSOLE()
#define FREE_CONSOLE()
#endif

template<class T>
class Ringbuffer {
public:
    Ringbuffer(size_t initial_capacity = 0) :
        cap(initial_capacity), head(0), tail(0), full(false)
    {
        this->buf.resize(this->cap);
    }

    // Overflow policy is to overwrite the oldest entry
    void push(const T &data) {
        this->buf[head] = data;

        this->head = (this->head + 1) % this->cap;
        if(this->full) {
            this->tail = this->head;
        } else {
            this->full = this->head == this->tail;
        }
    }

    void clear() {
        this->head = 0;
        this->tail = 0;
        this->full = false;
    }

    void resize(size_t new_capacity) {
        this->clear();
        this->buf.resize(new_capacity);
        this->cap = new_capacity;
    }

    size_t size() {
        if (full) {
            return this->cap;
        } else if(head >= tail) {
            return head - tail;
        } else {
            return this->cap - tail + head;
        }
    }

    size_t capacity() {
        return this->cap;
    }

    T& operator[](size_t idx) {
        return buf[(head + this->cap - 1 - idx) % this->cap];
    }
private:
    std::vector<T> buf;
    size_t cap;
    size_t head;
    size_t tail;
    bool full;
};

enum class DebugConsoleLevel : uint8_t {
    Debug = 0,
    Info = 1,
    Warn = 2,
    Error = 3,
    Chain = 4,
};

struct DebugConsoleMessage {
    std::string message;
    std::chrono::time_point<std::chrono::system_clock> timestamp;
    DebugConsoleLevel level;
    bool truncated;
};

// DebugConsole, name shortened for easy retrieval from the global scope
class D {
public:
    TransactionLogger *tlogger;
    uint32_t tlogger_vsid_info;
    bool internal_buffer_enable;
    size_t internal_buffer_max_message_length;
    Ringbuffer<DebugConsoleMessage> internal_buffer;

    static D &get() {
        static D d;
        return d;
    }

    static void printmb(std::string_view multibyte) {
        std::wstring wide = convert_utf8_string_to_utf16_wstring(multibyte);
        WriteConsoleW(GetStdHandle(STD_OUTPUT_HANDLE), wide.data(), static_cast<DWORD>(wide.length()), NULL, NULL);
    }

    template<class... Args>
    void log(DebugConsoleLevel level, std::format_string<Args...> fmt, Args&&... args) {
        std::string multibyte = std::format(fmt, std::forward<Args>(args)...);
        auto now = std::chrono::system_clock::now();
        #ifdef SHOW_WIN32_CONSOLE
        if(level == DebugConsoleLevel::Chain) {
            printmb(multibyte);
        } else {
            printmb(std::format("amoeba - {:%F %T} - {}", now, multibyte));
        }
        #endif
        if(this->tlogger != nullptr) {
            this->tlogger->select_vsid(tlogger_vsid_info);
            if(level != DebugConsoleLevel::Chain) {
                this->tlogger->set_timestamp(now);
            }
            uint32_t user = 0;
            user |= (static_cast<uint8_t>(level) & 0xFF) << 0;
            this->tlogger->write_string(multibyte, user);
        }
        if(this->internal_buffer_enable) {
            if(level == DebugConsoleLevel::Chain && internal_buffer.size() > 0) {
                auto &last_message = internal_buffer[0];
                if(multibyte.length() + last_message.message.length() <= this->internal_buffer_max_message_length) {
                    last_message.message.append(multibyte);
                } else if (!last_message.truncated) {
                    size_t used = last_message.message.length();
                    size_t remaining = this->internal_buffer_max_message_length - used;
                    std::string sliced = multibyte.substr(0, remaining);
                    last_message.message.append(sliced);
                    last_message.truncated = true;
                }
                // NB if we allowed max message length to be dynamically upsized
                // we won't allow appends to an already truncated string
            } else {
                // if we receive a chainlink while the log is empty, place it in a new Debug level message
                DebugConsoleLevel effective_level = (level == DebugConsoleLevel::Chain) ? DebugConsoleLevel::Debug : level;
                if(multibyte.length() > this->internal_buffer_max_message_length) {
                    std::string sliced = multibyte.substr(0, this->internal_buffer_max_message_length);
                    DebugConsoleMessage dcm { .message = sliced, .timestamp = now, .level = effective_level, .truncated = true };
                    this->internal_buffer.push(dcm);
                } else {
                    DebugConsoleMessage dcm { .message = multibyte, .timestamp = now, .level = effective_level, .truncated = false };
                    this->internal_buffer.push(dcm);
                }
            }
        }
    }

    static void install_tlogger(TransactionLogger *tlogger, uint32_t tlogger_vsid_info) {
        D::get().tlogger = tlogger;
        D::get().tlogger_vsid_info = tlogger_vsid_info;
    }

    static void uninstall_tlogger() {
        D::get().tlogger = nullptr;
    }

    static void enable_internal_buffer(size_t max_messages, size_t max_message_length) {
        D::get().internal_buffer_enable = true;
        D::get().internal_buffer.resize(max_messages);
        D::get().internal_buffer_max_message_length = max_message_length;
    }

    static void disable_internal_buffer() {
        D::get().internal_buffer_enable = false;
        D::get().internal_buffer.clear();
    }

    template<class... Args>
    static void debug(std::format_string<Args...> fmt, Args&&... args) {
        D::get().log(DebugConsoleLevel::Debug, fmt, std::forward<Args>(args)...);
    }

    template<class... Args>
    static void info(std::format_string<Args...> fmt, Args&&... args) {
        D::get().log(DebugConsoleLevel::Info, fmt, std::forward<Args>(args)...);
    }

    template<class... Args>
    static void warn(std::format_string<Args...> fmt, Args&&... args) {
        D::get().log(DebugConsoleLevel::Warn, fmt, std::forward<Args>(args)...);
    }

    template<class... Args>
    static void error(std::format_string<Args...> fmt, Args&&... args) {
        D::get().log(DebugConsoleLevel::Error, fmt, std::forward<Args>(args)...);
    }

    // for now we assume logger users operate serially
    // can introduce a mutex to prevent interleaving if needed
    template<class... Args>
    static void chain(std::format_string<Args...> fmt, Args&&... args) {
        D::get().log(DebugConsoleLevel::Chain, fmt, std::forward<Args>(args)...);
    }

private:
    D() = default;
    ~D() = default;
    D(const D&) = delete;
    D& operator=(const D&) = delete;
    D(D&&) = delete;
    D& operator=(D&&) = delete;
};
