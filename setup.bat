@echo off
echo ============================================
echo  Project Eris - Installing dependencies
echo ============================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Install Python 3.13 first.
    pause & exit /b 1
)
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Installation failed. Check your internet connection.
    pause & exit /b 1
)
echo.
echo All packages installed. Run launch.bat to start.
pause
