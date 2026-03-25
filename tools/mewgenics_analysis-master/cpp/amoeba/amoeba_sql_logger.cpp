#include "amoeba.hpp"
#include "utilities/debug_console.hpp"
#include "utilities/function_hook.hpp"
// #include "utilities/msvcfunc_interceptor.hpp"
#include "types/msvc.hpp"
#include "types/glaiel.hpp"

#include <set>
#include <string>
#include <chrono>
#include <filesystem>

// Poor cat's SQL transaction logging
//
// Takes a copy of the save file every time Mewgenics
// flushes a transaction to disk via SQL COMMIT.
//
// Logs SQL queries issued by the game through its sqlite database connection.
//
// polymeric 2026

struct SqlLoggerPrivateState {
    uint32_t save_scope_counter;
    std::set<std::string> witnessed_db_paths;
};

static SqlLoggerPrivateState P;

void write_db_to_log(std::string file_path) {
    G.tlogger->select_vsid(TlogVsid::SaveData);
    G.tlogger->set_timestamp_now();
    #if defined(__clang__) && !defined(_MSC_VER)
    // libc++ does not implement clock_cast
    int64_t mtime = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::file_clock::to_sys(
            std::filesystem::last_write_time(file_path)
        ).time_since_epoch()
    ).count();
    #else
    // STL does not implement to_sys
    int64_t mtime = std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::clock_cast<std::chrono::system_clock>(
            std::filesystem::last_write_time(file_path)
        ).time_since_epoch()
    ).count();
    #endif
    if constexpr(TLOG_SCHEMA_VERSION_HINT > 0) {
        // relative to Unix epoch
        G.tlogger->write_int64(mtime);
    } else {
        // relative to Windows FILETIME epoch
        G.tlogger->write_int64(mtime + 11644473600000000);
    }
    G.tlogger->write_string(std::filesystem::path(file_path).filename().string());
    G.tlogger->write_blob_from_file(file_path);
}

void write_sql_to_log(std::string query, PodBufferPreallocated<SqlParam, 4> *params, std::string file_path) {
    G.tlogger->select_vsid(TlogVsid::Sql);
    G.tlogger->set_timestamp_now();
    if constexpr(TLOG_SCHEMA_VERSION_HINT > 0) {
        G.tlogger->write_string(std::filesystem::path(file_path).filename().string());
    }
    G.tlogger->write_int64(params->size);
    G.tlogger->write_string(query);
    for(const auto &param : *params) {
        G.tlogger->write_string(param.name);
        switch(param.data.type) {
            case Blob:
                G.tlogger->write_blob(param.data.value.as_blob_ptr, param.data.length);
                break;
            case Text:
                G.tlogger->write_string(param.data.value.as_c_str);
                break;
            // case WText:
            //     s += std::format("L\"{}\"", param.data.value.as_wc_str);
            //     break;
            // case Integer32:
            //     G.tlogger->write_int64(param.data.value.as_int);
            //     break;
            case Integer:
                G.tlogger->write_int64(param.data.value.as_int64);
                break;
            case Real:
                G.tlogger->write_double(param.data.value.as_double);
                break;
            default:
                G.tlogger->write_na();
                break;
        }
    }
}

MAKE_HOOK(ADDRESS_glaiel__SQLSaveFile__BeginSave,
    void, __cdecl, glaiel__SQLSaveFile__BeginSave,
    SQLSaveFile* thiss
) {
    if(P.save_scope_counter == 0) {
        D::info("BEGIN TRANSACTION will be issued - {}\n", std::filesystem::path(thiss->file_path.copy_to_native_string()).filename().string());
        P.save_scope_counter++;
    } else {
        P.save_scope_counter++;
    }

    glaiel__SQLSaveFile__BeginSave_hook.orig(thiss);
}

MAKE_HOOK(ADDRESS_glaiel__SQLSaveFile__EndSave,
    void, __cdecl, glaiel__SQLSaveFile__EndSave,
    SQLSaveFile* thiss
) {
    glaiel__SQLSaveFile__EndSave_hook.orig(thiss);

    if(P.save_scope_counter == 1) {
        D::info("COMMIT was issued - {}\n", std::filesystem::path(thiss->file_path.copy_to_native_string()).filename().string());
        write_db_to_log(thiss->file_path);
        P.save_scope_counter--;
    } else if (P.save_scope_counter == 0) {
        D::warn("Save scope counter underflowed--maybe this hook was injected while the game was saving\n", static_cast<void *>(thiss));
    } else {
        P.save_scope_counter--;
    }
}

MAKE_HOOK(ADDRESS_glaiel__SQLSaveFile__SQL,
    void, __cdecl, glaiel__SQLSaveFile__SQL,
    SQLSaveFile *thiss, MsvcReleaseModeXString *ref_query, PodBufferPreallocated<SqlParam, 4> *params, MsvcFuncNoAlloc<glaiel__SQLSaveFile__SQL_CallableLayout1, void (sqlite3_stmt *p_stmt)> *ref_callback
) {
    // int n_rows = 0;
    // using CallbackWrapper = MsvcFuncNoAllocWrapper<glaiel__SQLSaveFile__SQL_CallableLayout1, void (sqlite3_stmt *p_stmt)>;
    // std::function lambda = [&n_rows](CallbackWrapper::Wrapper *thiss, sqlite3_stmt **pp_stmt) -> void {
    //     CallbackWrapper::Wrapped *wrapped = thiss->_Mystorage._Callee.wrapped;
    //     wrapped->vtable->_Do_call(wrapped, pp_stmt);
    //     // FIXME we need to discriminate the actual capture layout based on wrapped->vtable
    //     // or some other determinant, since multiple variants do exist (e.g. value reads,
    //     // PRAGMA reads, MAX(key) reads), or work with sqlite directly
    //     // For now we assume the 7-qword capture buffer is always readable,
    //     // and parse the most common case of a value read
    //     D::chain("    resp datatype {}\n", *wrapped->_Mystorage._Callee.sqlite3_datatype);
    //     D::chain("    resp pdata {:p}\n", (void*)wrapped->_Mystorage._Callee.result);
    //     // FIXME reals don't parse correctly, strange
    //     D::chain("    resp data {}\n", wrapped->_Mystorage._Callee.result->untrusted_format());
    //     n_rows++;
    // };
    // CallbackWrapper callback_wrapper(ref_callback, &lambda);

    // our only opportunity to sample query is before it is passed to the original function
    std::string query_clone = ref_query->copy_to_native_string();

    // D::debug("{}", query_clone);
    // for(const auto &param : *params) {
    //     D::chain(" {}", param);
    // }
    // D::chain("\n");

    // query will be destroyed inside the original function
    // callback will be destroyed by proxy through the wrapper in the original function
    glaiel__SQLSaveFile__SQL_hook.orig(thiss, ref_query, params, ref_callback);
    // glaiel__SQLSaveFile__SQL_hook.orig(thiss, ref_query, params, callback_wrapper.as_target_type());

    // D::chain("    resp n rows: {}\n", n_rows);

    // log the save file if it is the first time we witnessed it referenced
    // TODO does not account for in-game savefile deletes
    if(P.witnessed_db_paths.insert(thiss->file_path).second) {
        write_db_to_log(thiss->file_path);
    }

    // Currently only captures queries within a transaction scope
    // This effectively restricts our log to only include write-related queries
    // TODO make query dumping configurable, still neat to see when the game decides to query a variable
    if(P.save_scope_counter > 0) {
        write_sql_to_log(query_clone, params, thiss->file_path);
    }
}
