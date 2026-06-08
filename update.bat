@echo off
chcp 65001 >nul
setlocal

set INSTALL_DIR=C:\ImpactLED\Bootsi
set REPO=Sacton86/Bootsi
set BASE_URL=https://github.com/%REPO%/releases/latest/download

echo.
echo  ============================================================
echo   Bootsi  ^|  Manual Updater
echo  ============================================================
echo.

:: --- Admin check ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] This updater must be run as Administrator.
    echo  Right-click the script and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: --- Install check ---
if not exist "%INSTALL_DIR%\Bootsi.exe" (
    echo  [ERROR] Bootsi does not appear to be installed at %INSTALL_DIR%
    echo  Please run install.bat first.
    echo.
    pause
    exit /b 1
)

echo  Updating Bootsi in %INSTALL_DIR%...
echo.

echo  [1/4] Stopping any running instances...
taskkill /f /im Bootsi.exe >nul 2>&1
timeout /t 1 /nobreak >nul

echo  [2/4] Downloading latest Bootsi.exe...
curl -L --progress-bar -o "%INSTALL_DIR%\Bootsi.exe" "%BASE_URL%/Bootsi.exe"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to download Bootsi.exe
    pause & exit /b 1
)

echo  [3/4] Downloading latest assets...
curl -L --progress-bar -o "%TEMP%\bootsi-assets.zip" "%BASE_URL%/bootsi-assets.zip"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to download bootsi-assets.zip
    pause & exit /b 1
)

echo  [4/4] Extracting assets...
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP%\bootsi-assets.zip' -DestinationPath '%INSTALL_DIR%' -Force"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to extract assets
    pause & exit /b 1
)
del "%TEMP%\bootsi-assets.zip" >nul 2>&1

echo.
echo  ============================================================
echo   Bootsi updated successfully!
echo   Location : %INSTALL_DIR%\Bootsi.exe
echo  ============================================================
echo.
pause
