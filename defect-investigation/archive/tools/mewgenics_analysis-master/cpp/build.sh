#!/bin/sh
if [ -z "$1" ]; then
    exit 1
fi

cmake -S . -B ../out/cmake/$1/

cd ../out/cmake/$1/
cmake --build . --config RelWithDebInfo --parallel
cmake --install . --config RelWithDebInfo --prefix=install
