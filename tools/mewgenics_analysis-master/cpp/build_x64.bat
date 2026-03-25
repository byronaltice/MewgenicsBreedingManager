cmake -S . -B ..\out\cmake\x64\ -A x64

pushd ..\out\cmake\x64\
cmake --build . --config RelWithDebInfo --parallel
cmake --install . --config RelWithDebInfo --prefix=install
popd

pause
