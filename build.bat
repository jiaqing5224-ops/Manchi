@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Manchi Build

set "SCRIPT_DIR=%~dp0"
REM Python interpreter selection (in order of preference):
REM   1. MANCHI_PYTHON env var if explicitly set
REM   2. The 'airun' conda environment (the designated build environment,
REM      which has PyInstaller, the backend deps, and the required DLLs)
REM   3. System 'python' on PATH
if defined MANCHI_PYTHON (
    set "PYTHON=%MANCHI_PYTHON%"
) else if exist "%LOCALAPPDATA%\miniforge3\envs\airun\python.exe" (
    set "PYTHON=%LOCALAPPDATA%\miniforge3\envs\airun\python.exe"
) else (
    set "PYTHON=python"
)
set "BACKEND_DIR=%SCRIPT_DIR%backend"
REM The backend build runs with the same Python selected above (airun by
REM default). build_backend.py invokes PyInstaller via sys.executable, so
REM the chosen interpreter must have PyInstaller + backend deps installed.
set "BACKEND_PYTHON=%PYTHON%"
set "FRONTEND_DIR=%SCRIPT_DIR%frontend\manchi-ui"
set "PROJECT_CACHE=%SCRIPT_DIR%.build-cache\electron-builder"
set "SYS_CACHE=%LOCALAPPDATA%\electron-builder\Cache"
set "CSC_IDENTITY_AUTO_DISCOVERY=false"

call :main %*
set "EXIT_CODE=%ERRORLEVEL%"

if defined BUILD_RELAUNCHED exit /b %EXIT_CODE%

echo.
echo ============================================
if "%EXIT_CODE%"=="0" (
    echo   Build complete!
    echo   Installer: %FRONTEND_DIR%\dist\
) else (
    echo   Build failed. See the error above.
)
echo ============================================
echo.
pause
exit /b %EXIT_CODE%

:main
echo ============================================
echo   Manchi Build Script
echo ============================================
echo.

REM Check for Administrator privileges. electron-builder may need this when
REM extracting winCodeSign archives that contain symbolic links.
net session >nul 2>&1
if errorlevel 1 (
    if /i "%~1"=="--elevated" (
        echo [ERROR] Still not running as administrator.
        echo [ERROR] Please right-click build.bat and choose Run as administrator.
        exit /b 1
    )

    echo [BUILD] Administrator privileges required.
    echo [BUILD] Requesting elevation. Please approve the UAC prompt.
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '--elevated' -Verb RunAs"
    if errorlevel 1 (
        echo [ERROR] Failed to start the elevated build window.
        exit /b 1
    )

    echo [BUILD] Elevated build window started.
    echo [BUILD] This window will close in a few seconds.
    timeout /t 5 /nobreak >nul
    set "BUILD_RELAUNCHED=1"
    exit /b 0
)

if not exist "%PYTHON%" (
    echo [ERROR] Python not found: %PYTHON%
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
echo [1/4] Setting up build cache (winCodeSign, NSIS)...
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

REM ---- Step 2: Build Backend ----
echo [2/4] Building backend with PyInstaller...
cd /d "%BACKEND_DIR%" || exit /b 1
"%BACKEND_PYTHON%" build_backend.py
if errorlevel 1 (
    echo [ERROR] Backend build failed.
    exit /b 1
)

REM ---- Step 3: Install Frontend Dependencies ----
echo [3/4] Installing frontend dependencies...
cd /d "%FRONTEND_DIR%" || exit /b 1
call npm install
if errorlevel 1 (
    echo [ERROR] npm install failed.
    exit /b 1
)

REM ---- Step 4: Build Electron Package ----
echo [4/4] Building Electron installer...
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
