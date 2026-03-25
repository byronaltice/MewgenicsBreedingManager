cmake_minimum_required(VERSION 3.15)

project(sqlite3)

# Set language mode
set(CMAKE_C_STANDARD 17)
set(CMAKE_C_STANDARD_REQUIRED ON)
# possibly does nothing with MSVC
set(CMAKE_C_EXTENSIONS OFF)

set(SQLITE3_AMALGAMATION_DIR third_party/sqlite-amalgamation-3380500)

if(MSVC)
    add_compile_options(/W4)
elseif(MINGW)
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Define build targets
add_library(sqlite3 STATIC
    ${SQLITE3_AMALGAMATION_DIR}/sqlite3.c
    #${SQLITE3_AMALGAMATION_DIR}/shell.c
)

target_include_directories(sqlite3 PUBLIC
    ${SQLITE3_AMALGAMATION_DIR}
)
