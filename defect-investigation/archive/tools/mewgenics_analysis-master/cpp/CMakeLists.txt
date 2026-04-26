cmake_minimum_required(VERSION 3.15)

project(mewgenics_analysis)

# Read third-party library CMakeLists
add_subdirectory(lib/minhook EXCLUDE_FROM_ALL)
add_subdirectory(lib/lz4/build/cmake EXCLUDE_FROM_ALL)
add_subdirectory(lib/cmake/detours EXCLUDE_FROM_ALL)
add_subdirectory(lib/cmake/SDL EXCLUDE_FROM_ALL)
add_subdirectory(lib/cmake/imgui EXCLUDE_FROM_ALL)
add_subdirectory(lib/Mewgenics EXCLUDE_FROM_ALL)
add_subdirectory(lib/sqlite3 EXCLUDE_FROM_ALL)

# Read our CMakeLists
add_subdirectory(amoeba)
add_subdirectory(cosmic_ooze)
