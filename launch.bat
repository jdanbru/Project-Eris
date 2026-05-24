@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
    echo ERROR: Project Eris failed to start. Run setup.bat first.
    pause
)
