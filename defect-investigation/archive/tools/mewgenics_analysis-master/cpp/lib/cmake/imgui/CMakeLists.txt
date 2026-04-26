cmake_minimum_required(VERSION 3.15)

project(dear_imgui)

# Set language mode
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# possibly does nothing with MSVC; permissive- is set by std:c++20
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    if (CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
        add_compile_options(/W4)
    else()
        # clean with MSVC
        add_compile_options(/W4)
    endif()
elseif(MINGW)
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Build Dear ImGui and SDL3/OpenGL backends
set(DEAR_IMGUI_DIR ../../imgui)

file(GLOB IMGUI_SRC ${DEAR_IMGUI_DIR}/imgui*.cpp)
add_library(dear_imgui STATIC
    ${DEAR_IMGUI_DIR}/imgui.cpp
    ${DEAR_IMGUI_DIR}/imgui_demo.cpp
    ${DEAR_IMGUI_DIR}/imgui_draw.cpp
    ${DEAR_IMGUI_DIR}/imgui_tables.cpp
    ${DEAR_IMGUI_DIR}/imgui_widgets.cpp
    ${DEAR_IMGUI_DIR}/backends/imgui_impl_sdl3.cpp
    ${DEAR_IMGUI_DIR}/backends/imgui_impl_opengl3.cpp
)

target_link_libraries(dear_imgui PRIVATE SDL3::Headers)

target_include_directories(dear_imgui PUBLIC
    ${DEAR_IMGUI_DIR}
    ${DEAR_IMGUI_DIR}/backends
)
