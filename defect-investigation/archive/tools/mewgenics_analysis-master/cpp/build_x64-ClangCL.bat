cmake -S . -B ..\out\cmake\x64-ClangCL\ -A x64 -T ClangCL

pushd ..\out\cmake\x64-ClangCL\
cmake --build . --config RelWithDebInfo --parallel
cmake --install . --config RelWithDebInfo --prefix=install
popd

pause
