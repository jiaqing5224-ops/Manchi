@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "LOG=%SCRIPT_DIR%build.log"
set "DIAG=%SCRIPT_DIR%build.diag.log"

REM Diagnostic trace (independent of the tee wrapper, always written) so a
REM failure is never a silent auto-close: build.diag.log records how far we got.
echo [%date% %time%] build.bat launched > "%DIAG%"
echo   SCRIPT_DIR=%SCRIPT_DIR% >> "%DIAG%"
echo   MANCHI_TEE=%MANCHI_TEE% >> "%DIAG%"

REM ---------------------------------------------------------------------------
REM Python interpreter selection (in order of preference):
REM   1. MANCHI_PYTHON env var if explicitly set
REM   2. The 'airun' conda environment (designated build env; has the tooling
REM      needed to run setup_build_cache.py, npm, etc.)
REM   3. System 'python' on PATH
REM
REM NOTE: The shipped product no longer uses a PyInstaller-frozen backend.
REM Instead the backend is bundled as SOURCE and run through a dedicated,
REM user-writable venv (see frontend/manchi-ui/electron/main/backend.ts +
REM backend/scripts/bootstrap_runtime.py). That venv is bootstrapped on first
REM launch from a *portable* full CPython copied into backend/dist/python
REM during this build (Step 2) -- or, failing that, from a system Python.
REM ---------------------------------------------------------------------------
if defined MANCHI_PYTHON (
    set "PYTHON=%MANCHI_PYTHON%"
) else if exist "%LOCALAPPDATA%\miniforge3\envs\airun\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\miniforge3\envs\airun\python.exe"
) else (
    set "PYTHON=python"
)
set "BACKEND_DIR=%SCRIPT_DIR%backend"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend\manchi-ui"
set "PROJECT_CACHE=%SCRIPT_DIR%.build-cache\electron-builder"
set "SYS_CACHE=%LOCALAPPDATA%\electron-builder\Cache"
set "CSC_IDENTITY_AUTO_DISCOVERY=false"

REM ---------------------------------------------------------------------------
REM Local caches so the build does NOT re-download from the network every run.
REM   NPM_CONFIG_CACHE -> npm tarballs (npm uses this with --prefer-offline)
REM   ELECTRON_CACHE   -> downloaded electron binary + headers (used by
REM                      electron-builder install-app-deps and packaging)
REM These live under .build-cache (already used for winCodeSign/nsis), so a
REM single network build populates them and all later builds run offline.
REM ---- REM To go STRICTLY offline after the first build, change
REM      --prefer-offline to --offline below. ----
REM ---------------------------------------------------------------------------
set "NPM_CONFIG_CACHE=%SCRIPT_DIR%.build-cache\npm-cache"
set "ELECTRON_CACHE=%SCRIPT_DIR%.build-cache\electron"

REM ---------------------------------------------------------------------------
REM If we are not already inside the tee wrapper, re-launch through a small
REM PowerShell helper (tee_build.ps1) so output is shown LIVE on the console
REM AND saved to build.log. We use -File (not -Command) to avoid fragile
REM batch-vs-PowerShell quote escaping. If tee is unavailable, fall back to
REM running directly (console output only; the final pause keeps the window
REM open and build.diag.log still records progress).
REM ---------------------------------------------------------------------------
if not defined MANCHI_TEE (
    set "MANCHI_TEE=1"
    echo [%date% %time%] launching tee helper via powershell -File tee_build.ps1 ... >> "%DIAG%"
    powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%tee_build.ps1" "%~f0" "%LOG%"
    set "RC=%ERRORLEVEL%"
    echo [%date% %time%] tee helper returned RC=%RC% >> "%DIAG%"
    if not "%RC%"=="0" (
        echo [WARN] Live logging unavailable; running directly with console output.
        goto :run
    )
    exit /b
)

:run
chcp 65001 >nul
title Manchi Build
echo [%date% %time%] === Manchi build started ===
echo [%date% %time%] PYTHON=%PYTHON% >> "%DIAG%"
call :main %*
set "EXIT_CODE=%ERRORLEVEL%"
goto :finish

:main
echo ============================================
echo   Manchi Build Script
echo ============================================
echo.

REM Check for Administrator privileges. electron-builder may need this when
REM extracting winCodeSign archives that contain symbolic links.
REM We do NOT auto-elevate (a spawned elevated window can flash and close with
REM no visible error). Instead we require the user to launch us as admin.
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] This script must be run as Administrator.
    echo [ERROR] Close this window, right-click build.bat, and choose
    echo [ERROR] "Run as administrator".
    echo.
    pause < con
    exit /b 1
)

"%PYTHON%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found or not working: %PYTHON%
    echo [ERROR] Set MANCHI_PYTHON to a working python.exe, or install Python.
    exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found in PATH.
    exit /b 1
)

where npx >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npx was not found in PATH.
    exit /b 1
)

REM ---- Step 1: Setup build cache ----
echo [%time%] [1/4] Setting up build cache (winCodeSign, NSIS)...
cd /d "%SCRIPT_DIR%" || exit /b 1
"%PYTHON%" setup_build_cache.py
if errorlevel 1 (
    echo [ERROR] setup_build_cache.py failed.
    exit /b 1
)

if exist "%PROJECT_CACHE%" (
    echo Copying project cache to system cache...
    if not exist "%SYS_CACHE%" mkdir "%SYS_CACHE%"
    xcopy "%PROJECT_CACHE%\*" "%SYS_CACHE%\" /E /I /Q /Y >nul
    if errorlevel 1 (
        echo [ERROR] Failed to copy build cache to: %SYS_CACHE%
        exit /b 1
    )
    echo Cache ready: %SYS_CACHE%
)

REM ---- Step 2: Stage portable Python runtime ----
REM Copy a FULL standard CPython (must include pip + venv + ensurepip) into
REM backend/dist/python. The first-launch bootstrap (bootstrap_runtime.py)
REM builds the runtime venv from this copy, so clean machines (no system
REM Python) can still bootstrap. Prefer C:\Program Files\Python3XX; override
REM with MANCHI_BUNDLE_PYTHON if needed.
echo [%time%] [2/4] Staging portable Python runtime...
set "BUNDLE_SRC="
if defined MANCHI_BUNDLE_PYTHON (
    set "BUNDLE_SRC=%MANCHI_BUNDLE_PYTHON%"
) else if exist "C:\Program Files\Python311" (
    set "BUNDLE_SRC=C:\Program Files\Python311"
) else (
    for /d %%D in ("C:\Program Files\Python3*") do (
        if not defined BUNDLE_SRC set "BUNDLE_SRC=%%D"
    )
)
set "DST=%BACKEND_DIR%\dist\python"
if exist "%DST%" rmdir /s /q "%DST%"
if defined BUNDLE_SRC (
    if exist "%BUNDLE_SRC%\python.exe" (
        echo   Staging from: %BUNDLE_SRC%
        robocopy "%BUNDLE_SRC%" "%DST%" /E ^
            /XD "test" "tkinter" "idlelib" "site-packages" ^
                "tcl" "Tools" "Doc" "include" ^
            /NFL /NDL /NJH /NJS
        if errorlevel 8 (
            echo [ERROR] Failed to stage portable Python via robocopy.
            exit /b 1
        )
        echo   Portable Python staged at: %DST%
    ) else (
        echo [ERROR] BUNDLE_SRC set but python.exe missing: %BUNDLE_SRC%
        exit /b 1
    )
) else (
    echo [WARN] No standard CPython found under "C:\Program Files\Python3*".
    echo [WARN] Skipping Python bundling. The shipped app will fall back to a
    echo [WARN] system Python at first launch; clean machines without one will
    echo [WARN] be unable to bootstrap the runtime. Install standard Python or
    echo [WARN] set MANCHI_BUNDLE_PYTHON to bundle it.
)

REM ---- Step 3: Install Frontend Dependencies ----
echo [%time%] [3/4] Installing frontend dependencies...
cd /d "%FRONTEND_DIR%" || exit /b 1
call npm install --prefer-offline --no-audit --no-fund
if errorlevel 1 (
    echo [ERROR] npm install failed.
    exit /b 1
)

REM ---- Step 4: Build Electron Package ----
echo [%time%] [4/4] Building Electron installer...
call npx electron-vite build
if errorlevel 1 (
    echo [ERROR] electron-vite build failed.
    exit /b 1
)

call npx electron-builder build --win --config electron-builder.yml
if errorlevel 1 (
    echo [ERROR] electron-builder packaging failed.
    exit /b 1
)

exit /b 0

:finish
echo [%time%] === Manchi build finished ===
echo.
echo ============================================
if "%EXIT_CODE%"=="0" (
    echo   Build complete!
    echo   Installer: %FRONTEND_DIR%\dist\
) else (
    echo   Build failed.
)
echo ============================================
echo.
echo Logs written:
echo   build.log      : %LOG%
echo   build.diag.log : %DIAG%
echo.
pause < con
exit /b %EXIT_CODE%
