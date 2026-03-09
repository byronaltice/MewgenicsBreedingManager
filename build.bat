@echo off
cd /d "%~dp0"
set "BUILD_DIR=build\mewgenics_manager"
set "DIST_ROOT=dist"
set "APP_DIR_OUT=%DIST_ROOT%\MewgenicsManager"
set "APP_EXE_OUT=%DIST_ROOT%\MewgenicsManager.exe"

echo Installing / updating dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Cleaning previous build output...
if exist "%APP_DIR_OUT%" (
    attrib -R /S /D "%APP_DIR_OUT%\*" >nul 2>nul
    rmdir /S /Q "%APP_DIR_OUT%"
)
if exist "%APP_DIR_OUT%" (
    echo Warning: could not remove %APP_DIR_OUT%. Continuing with onefile build.
)
if exist "%APP_EXE_OUT%" (
    attrib -R "%APP_EXE_OUT%" >nul 2>nul
    del /F /Q "%APP_EXE_OUT%"
)
if exist "%BUILD_DIR%" (
    attrib -R /S /D "%BUILD_DIR%\*" >nul 2>nul
    rmdir /S /Q "%BUILD_DIR%"
)

echo.
echo Building standalone executable...
pyinstaller mewgenics_manager.spec --noconfirm --distpath "%DIST_ROOT%"

echo.
if exist "%APP_EXE_OUT%" (
    echo Build succeeded!
    echo Executable: %APP_EXE_OUT%
) else (
    echo Build FAILED - check output above.
)
pause
