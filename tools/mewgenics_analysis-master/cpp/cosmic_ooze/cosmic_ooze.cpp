// #define ENABLE_DEBUG_CONSOLE

#include <string>
#include <format>
#include <filesystem>
#include <iostream>

#include <windows.h>
#include <tlhelp32.h>

#include "detours.h"

// Kitty's first DLL injector (TM)
//
// - cosmic_ooze.exe and amoeba.dll must be placed in the same directory.
// - When cosmic_ooze is launched, amoeba.dll will be injected into a running Mewgenics instance.
// - If cosmic_ooze and amoeba are (optionally) placed in the same directory as Mewgenics.exe,
//   cosmic_ooze will also launch Mewgenics if it is not already running, before injecting amoeba.dll.
//
// ♪ alien crater ♪ feline invader ♪
//
// polymeric 2026

const WCHAR TARGET_EXE_NAME[] = L"Mewgenics.exe";
const WCHAR TARGET_STEAM_APP_ID[] = L"686060";
const WCHAR DLL_NAME[] = L"amoeba.dll";

bool try_hook_process(DWORD pid, std::filesystem::path dll_path_relative_to_loader) {
    // LoadLibrary-based injector, for hooking existing processes
    if(pid == 0) {
        return false;
    }

    std::filesystem::path abs_dll_path = std::filesystem::canonical(dll_path_relative_to_loader);

    if(!std::filesystem::is_regular_file(abs_dll_path)) {
        return false;
    }

    HANDLE h_process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION | PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ, FALSE, pid);
    if(h_process == NULL) {
        return false;
    }

    size_t sizeof_abs_dll_path_bytes = (abs_dll_path.wstring().size() + 1) * sizeof(wchar_t);

    PVOID mem = VirtualAllocEx(h_process, NULL, sizeof_abs_dll_path_bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if(mem == NULL) {
        CloseHandle(h_process);
        return false;
    }

    if(!WriteProcessMemory(h_process, mem, abs_dll_path.c_str(), sizeof_abs_dll_path_bytes, NULL)) {
        VirtualFreeEx(h_process, mem, 0, MEM_RELEASE);
        CloseHandle(h_process);
        return false;
    }

    // LoadLibraryW is located at the same VA within all processes that have kernel32.dll mapped.
    // Key trick is to extract its address from our process and call the same address from the target.
    LPTHREAD_START_ROUTINE p_LoadLibraryW = reinterpret_cast<LPTHREAD_START_ROUTINE>(reinterpret_cast<void *>(&LoadLibraryW));
    HANDLE h_thread = CreateRemoteThread(h_process, NULL, 0, p_LoadLibraryW, mem, 0, NULL);
    if(h_thread == NULL) {
        VirtualFreeEx(h_process, mem, 0, MEM_RELEASE);
        CloseHandle(h_process);
        return false;
    }

    WaitForSingleObject(h_thread, INFINITE);

    CloseHandle(h_thread);
    VirtualFreeEx(h_process, mem, 0, MEM_RELEASE);
    CloseHandle(h_process);
    return true;
}

DWORD try_find_process(std::wstring target_executable_name) {
    HANDLE h_process_snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if(h_process_snapshot == INVALID_HANDLE_VALUE) {
        return 0;
    }

    PROCESSENTRY32W pe32w;
    pe32w.dwSize = sizeof(PROCESSENTRY32W);

    if(!Process32FirstW(h_process_snapshot, &pe32w)) {
        CloseHandle(h_process_snapshot);
        return 0;
    }

    DWORD pid = 0;

    do {
        if(_wcsicmp(target_executable_name.c_str(), pe32w.szExeFile) == 0) {
            pid = pe32w.th32ProcessID;
            break;
        }
    } while(Process32NextW(h_process_snapshot, &pe32w));

    CloseHandle(h_process_snapshot);

    return pid;
}

DWORD try_launch_process(std::filesystem::path target_executable_path_relative_to_loader, std::filesystem::path dll_path_relative_to_target_executable) {
    // White-label wrapper around Detours CreateProcessWithDll, for hooking new processes
    // Detours' technique ensures the hook is installed before the host process starts executing its own user code
    STARTUPINFOW startup_info = {};
    startup_info.cb = sizeof(STARTUPINFOW);
    PROCESS_INFORMATION process_info = {};

    std::filesystem::path abs_target_executable_path = std::filesystem::canonical(target_executable_path_relative_to_loader);

    if(!std::filesystem::is_regular_file(abs_target_executable_path)) {
        return 0;
    }

    if(!std::filesystem::is_regular_file(abs_target_executable_path.parent_path() / dll_path_relative_to_target_executable)) {
        return 0;
    }

    if(!DetourCreateProcessWithDllExW(
        abs_target_executable_path.c_str(),
        NULL,
        NULL,
        NULL,
        FALSE,
        0,
        NULL,
        // must be absolute
        abs_target_executable_path.parent_path().c_str(),
        &startup_info,
        &process_info,
        // Consumed by a low-level structure that only understands narrow strings.
        // In practice, we should only use ANSI characters in our dll name and should locate
        // it in the same directory as the target executable, so that the relative path
        // from the target to the dll can always be captured in a narrow string.
        dll_path_relative_to_target_executable.string().c_str(),
        NULL
    )) {
        return 0;
    }

    return process_info.dwProcessId;
}

int WINAPI wWinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance, PWSTR pCmdLine, int nCmdShow) {
    // unused arguments, suppresses C4100
    (void)hInstance;
    (void)hPrevInstance;
    (void)pCmdLine;
    (void)nCmdShow;

    #ifdef ENABLE_DEBUG_CONSOLE
    AllocConsole();
    FILE* dummy_p_file;
    freopen_s(&dummy_p_file, "CONIN$", "r", stdin);
    freopen_s(&dummy_p_file, "CONOUT$", "w", stderr);
    freopen_s(&dummy_p_file, "CONOUT$", "w", stdout);
    #endif

    std::wcout << std::format(L"Will attempt to hook {} (appid {}) with {}\n", TARGET_EXE_NAME, TARGET_STEAM_APP_ID, DLL_NAME);

    // Steamworks games will fork themselves if they do not know their appid and interfere with Detours injection.
    // We replicate what Steam would've done if it launched the executable by setting SteamAppId and SteamGameId.
    // We set these env vars in the parent environment, as EnvironmentStrings is unwieldy to edit.
    // Learned this trick through examining the Skyrim Script Extender :)
    SetEnvironmentVariableW(L"SteamAppId", TARGET_STEAM_APP_ID);
    SetEnvironmentVariableW(L"SteamGameId", TARGET_STEAM_APP_ID);

    DWORD pid = try_find_process(TARGET_EXE_NAME);

    if(pid == 0) {
        std::wcout << std::format(L"Did not find existing process\n");
        if (std::filesystem::is_regular_file(TARGET_EXE_NAME)) {
            pid = try_launch_process(TARGET_EXE_NAME, DLL_NAME);
            if(pid == 0) {
                std::wcout << std::format(L"Failed to launch new process\n");
                MessageBoxW(NULL, std::format(L"Failed to launch and hook {}", TARGET_EXE_NAME).c_str(), L"Error", MB_OK | MB_ICONEXCLAMATION);
            } else {
                std::wcout << std::format(L"Launched and hooked PID: {}\n", pid);
            }
        } else {
            MessageBoxW(NULL, std::format(L"Could not locate {}", TARGET_EXE_NAME).c_str(), L"Error", MB_OK | MB_ICONEXCLAMATION);
        }
    } else {
        std::wcout << std::format(L"Detected PID: {}\n", pid);
        if(true /* MessageBoxW(NULL, std::format(L"{} is already running. Would you like to hot-patch PID {}?", TARGET_EXE_NAME, pid).c_str(), L"Hot patch?", MB_YESNO | MB_ICONQUESTION) == IDYES */) {
            if(!try_hook_process(pid, DLL_NAME)) {
                std::wcout << std::format(L"Failed to hook PID: {}\n", pid);
                MessageBoxW(NULL, std::format(L"Failed to hook {} PID {}", TARGET_EXE_NAME, pid).c_str(), L"Error", MB_OK | MB_ICONEXCLAMATION);
            } else {
                std::wcout << std::format(L"Hooked PID: {}\n", pid);
            }
        }
    }

    #ifdef ENABLE_DEBUG_CONSOLE
    std::wcout << L"Press Enter to exit";
    std::wcin.ignore();
    #endif

    return 0;
}
