cmake_minimum_required(VERSION 3.15)

project(cosmic_ooze)

# Build target names
set(INJECTOR_NAME cosmic_ooze)

# Set language mode
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
# possibly does nothing with MSVC; permissive- is set by std:c++20
set(CMAKE_CXX_EXTENSIONS OFF)

if(MSVC)
    add_compile_options(/W4)
elseif(MINGW)
    add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# Define build targets
add_executable(${INJECTOR_NAME} WIN32
    cosmic_ooze.cpp
)

target_include_directories(${INJECTOR_NAME} PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}
)

if(MSVC)
elseif(MINGW)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "Clang")
        # Statically link libc++ (static-libstdc++ flag also covers libc++)
        target_link_options(${INJECTOR_NAME} PRIVATE -static-libstdc++)
    elseif(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        # Statically link libgcc/libstdc++/libwinpthread
        target_link_options(${INJECTOR_NAME} PRIVATE -static-libgcc -static-libstdc++ -static -lwinpthread -dynamic)
    endif()
    # Set -municode so that gcc/clang will use wWinMain as an entry point
    target_link_options(${INJECTOR_NAME} PRIVATE -municode)
endif()

target_link_libraries(${INJECTOR_NAME} PRIVATE
    Detours
)

install(TARGETS ${TARGET_NAME} ${INJECTOR_NAME} RUNTIME DESTINATION bin)

if(MSVC)
    install(FILES $<TARGET_PDB_FILE:${INJECTOR_NAME}> TYPE BIN OPTIONAL)
endif()
