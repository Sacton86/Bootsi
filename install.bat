@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: Display ASCII art by downloading art.txt (preserves UTF-8 encoding correctly)
curl -fsSL "https://raw.githubusercontent.com/Sacton86/Bootsi/main/art.txt" -o "%TEMP%\bootsi_art.tmp" 2>nul
if exist "%TEMP%\bootsi_art.tmp" (
    type "%TEMP%\bootsi_art.tmp"
    del "%TEMP%\bootsi_art.tmp" >nul 2>&1
)

echo.
echo  ============================================================
echo   Bootsi  ^|  Custom Firmware USB Tool  ^|  Installer v1.0
echo  ============================================================
echo   Installs to: C:\ImpactLED\Bootsi\
echo  ============================================================
echo.

:: --- Admin check ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] This installer must be run as Administrator.
    echo  Right-click the script and choose "Run as administrator".
    echo.
    pause
    exit /b 1
)

set INSTALL_DIR=C:\ImpactLED\Bootsi
set BASE_URL=https://github.com/Sacton86/Bootsi/releases/latest/download

echo  [1/4] Creating install directory...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if %errorlevel% neq 0 (
    echo  [ERROR] Could not create %INSTALL_DIR%
    pause & exit /b 1
)

echo  [2/4] Downloading Bootsi.exe...
curl -fL --progress-bar -o "%INSTALL_DIR%\Bootsi.exe" "%BASE_URL%/Bootsi.exe"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to download Bootsi.exe - check your connection or that a release exists.
    pause & exit /b 1
)

echo  [3/4] Downloading assets...
curl -fL --progress-bar -o "%TEMP%\bootsi-assets.zip" "%BASE_URL%/bootsi-assets.zip"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to download bootsi-assets.zip - check your connection or that a release exists.
    pause & exit /b 1
)

echo  [4/4] Extracting assets...
powershell -NoProfile -Command "Expand-Archive -Path '%TEMP%\bootsi-assets.zip' -DestinationPath '%INSTALL_DIR%' -Force"
if %errorlevel% neq 0 (
    echo  [ERROR] Failed to extract assets.
    pause & exit /b 1
)
del "%TEMP%\bootsi-assets.zip" >nul 2>&1

echo  Creating desktop shortcut...
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Bootsi.lnk'); $s.TargetPath = '%INSTALL_DIR%\Bootsi.exe'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Save()"

echo.
echo  ============================================================
echo   Installation complete!
echo   Location : %INSTALL_DIR%\Bootsi.exe
echo   Shortcut : Desktop\Bootsi.lnk
echo  ============================================================
echo.
pause
