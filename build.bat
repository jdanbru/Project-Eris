@echo off
cd /d "%~dp0"
echo ============================================
echo  Project Eris - Building portable EXE
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 ( echo ERROR: Python not found. & pause & exit /b 1 )

pip show pyinstaller >nul 2>&1
if errorlevel 1 ( pip install pyinstaller )

echo Finding CustomTkinter location...
for /f "delims=" %%i in ('python -c "import customtkinter,os;print(os.path.dirname(customtkinter.__file__))"') do set CTK_PATH=%%i
echo   CustomTkinter: %CTK_PATH%
echo.
echo Building... (2-5 minutes)

pyinstaller ^
  --noconfirm ^
  --onedir ^
  --windowed ^
  --name "ProjectEris" ^
  --icon "assets\logo.png" ^
  --add-data "%CTK_PATH%;customtkinter/" ^
  --add-data "assets;assets/" ^
  main.py

if errorlevel 1 (
    echo ERROR: Build failed.
    pause & exit /b 1
)

echo.
echo ============================================
echo  Build complete!
echo  Portable app: dist\ProjectEris\
echo  Copy that folder to any Windows PC.
echo  Run ProjectEris.exe - no install needed.
echo ============================================
pause
