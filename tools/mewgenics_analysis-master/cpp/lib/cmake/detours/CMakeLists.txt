cmake_minimum_required(VERSION 3.15)

project(Detours)

# Set language mode
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# possibly does nothing with MSVC; permissive- is set by std:c++20
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    if (CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
        # not clean with Clang in MSVC mode, suppress
        add_compile_options(/W0)
    else()
        # clean with MSVC
        add_compile_options(/W4)
    endif()
elseif(MINGW)
    # not clean with GCC/Clang in GCC mode, suppress
    add_compile_options(-w)
endif()

set(DETOURS_DIR ../../detours)

add_library(Detours STATIC
    ${DETOURS_DIR}/src/detours.cpp
    ${DETOURS_DIR}/src/modules.cpp
    ${DETOURS_DIR}/src/disasm.cpp
    #${DETOURS_DIR}/src/image.cpp
    ${DETOURS_DIR}/src/creatwth.cpp
    #${DETOURS_DIR}/src/disolx86.cpp
    #${DETOURS_DIR}/src/disolx64.cpp
    #${DETOURS_DIR}/src/disolia64.cpp
    #${DETOURS_DIR}/src/disolarm.cpp
    #${DETOURS_DIR}/src/disolarm64.cpp
)

target_include_directories(Detours PUBLIC
    ${DETOURS_DIR}/src
)
