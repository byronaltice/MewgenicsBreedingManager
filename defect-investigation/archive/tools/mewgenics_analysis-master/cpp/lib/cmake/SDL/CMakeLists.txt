cmake_minimum_required(VERSION 3.15)

# just the headers from SDL3
# nothing else to avoid invoking expensive configure routines
project(SDL3)

set(SDL3_DIR ../../SDL)

# excerpted from SDL's CMakeLists
add_library(SDL3_Headers INTERFACE)
add_library(SDL3::Headers ALIAS SDL3_Headers)
set_property(TARGET SDL3_Headers PROPERTY EXPORT_NAME "Headers")
target_include_directories(SDL3_Headers INTERFACE
    "${SDL3_DIR}/include"
)
