@echo off
setlocal EnableDelayedExpansion

rem Copy the most recent Mewgenics save (and its JSON sidecars) into a timestamped
rem subfolder under test-saves, preserving the original filenames.
rem Save location: %APPDATA%\Glaiel Games\Mewgenics\<steamid>\saves\*.sav

set "SAVES_ROOT=%APPDATA%\Glaiel Games\Mewgenics"
set "DEST=%~dp0"
if "%DEST:~-1%"=="\" set "DEST=%DEST:~0,-1%"

if not exist "%SAVES_ROOT%" (
    echo [refresh-save] Mewgenics save root not found:
    echo     %SAVES_ROOT%
    exit /b 1
)

set "LATEST_SAVE="
for /f "delims=" %%F in ('dir /b /s /o-d /a-d "%SAVES_ROOT%\*.sav" 2^>nul') do (
    if not defined LATEST_SAVE set "LATEST_SAVE=%%F"
)

if not defined LATEST_SAVE (
    echo [refresh-save] No .sav files found under:
    echo     %SAVES_ROOT%
    exit /b 1
)

for /f %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "STAMP=%%I"

for %%F in ("%LATEST_SAVE%") do set "SAVE_DIR=%%~dpF"
for %%F in ("%LATEST_SAVE%") do set "SAVE_BASE=%%~nF"

set "TARGET_DIR=%DEST%\%STAMP%"
mkdir "%TARGET_DIR%"

echo [refresh-save] Folder: %TARGET_DIR%

copy /Y "%LATEST_SAVE%" "%TARGET_DIR%\" >nul
if errorlevel 1 (
    echo [refresh-save] Copy failed: %LATEST_SAVE%
    exit /b 1
)
echo     copied: %SAVE_BASE%.sav

for /f "delims=" %%J in ('dir /b /a-d "%SAVE_DIR%%SAVE_BASE%*.json" 2^>nul') do (
    copy /Y "%SAVE_DIR%%%J" "%TARGET_DIR%\" >nul
    if not errorlevel 1 (
        echo     copied: %%J
    )
)

endlocal
