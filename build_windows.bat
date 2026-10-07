@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first. & pause & exit /b 1)

".venv\Scripts\python.exe" -m PyInstaller --version >nul 2>nul
if errorlevel 1 (
  echo Installing the Windows packaging tool...
  ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt || (echo [!] Could not install PyInstaller. Check your internet connection. & pause & exit /b 1)
)

echo Building the standalone Windows app...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name TheLastHope --distpath dist --workpath build --specpath build --add-data "%CD%\pages;pages" --add-data "%CD%\templates;templates" --add-data "%CD%\static;static" --add-data "%CD%\team.json;." --add-data "%CD%\data.json;." --add-data "%CD%\data.sample.json;." --hidden-import models portable_launcher.py
if errorlevel 1 (echo [!] Build failed. & pause & exit /b 1)

echo.
echo Done: dist\TheLastHope.exe
echo Upload this single EXE to GitHub Releases. The target PC does not need Python.
pause