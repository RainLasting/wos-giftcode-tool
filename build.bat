@echo off
echo ============================================
echo  WOS Gift Code Tool - PyInstaller Build
echo ============================================
echo.

pip install pyinstaller --quiet 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller install failed
    pause
    exit /b 1
)

echo [1/5] Validating model files...
if not exist "model\captcha_model.onnx" (
    echo [ERROR] captcha_model.onnx not found in model directory!
    pause
    exit /b 1
)
if not exist "model\captcha_model_metadata.json" (
    echo [ERROR] captcha_model_metadata.json not found in model directory!
    pause
    exit /b 1
)
echo Model files validated OK.

echo [2/5] Cleaning old build files...
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo [3/5] Building with PyInstaller...
pyinstaller WOSGiftCodeTool.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the error messages above.
    pause
    exit /b 1
)

echo [4/5] Copying model files and generating player.csv...
if not exist "dist\model" mkdir "dist\model"
copy /y "model\captcha_model.onnx" "dist\model\" >nul
copy /y "model\captcha_model_metadata.json" "dist\model\" >nul
type nul > "dist\player.csv"

echo Verifying dist structure...
if not exist "dist\WOSGiftCodeTool.exe" (
    echo [ERROR] EXE not found in dist!
    pause
    exit /b 1
)
if not exist "dist\model\captcha_model.onnx" (
    echo [ERROR] Model file not copied to dist!
    pause
    exit /b 1
)

echo [5/5] Cleaning intermediate build files...
if exist "build" rmdir /s /q build
for /d %%d in (__pycache__) do (
    if exist "%%d" rmdir /s /q "%%d"
)

echo.
echo ============================================
echo  Build complete!
echo ============================================
echo.
echo Output directory: dist\
echo.
echo Files in dist:
echo   WOSGiftCodeTool.exe
echo   model\
echo     captcha_model.onnx
echo     captcha_model_metadata.json
echo   player.csv
echo.
echo Usage:
echo   1. Copy entire dist\ folder to target location
echo   2. Edit player.csv to add player IDs (one per line)
echo   3. Double-click exe to run
echo.
echo Required directory structure:
echo   Target\
echo   +-- WOSGiftCodeTool.exe
echo   +-- model\
echo   ^|   +-- captcha_model.onnx
echo   ^|   +-- captcha_model_metadata.json
echo   +-- player.csv
echo.
pause
