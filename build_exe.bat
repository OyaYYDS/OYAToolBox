@echo off
setlocal
cd /d "%~dp0"

echo [1/2] Clean old build artifacts...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [2/2] Building exe with PyInstaller...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --windowed ^
  --name "OYAToolBox" ^
  --icon "OYAToolBoxICO.ico" ^
  --collect-all PySide6 ^
  --add-data "web;web" ^
  --add-data "data;data" ^
  --add-data "OYAToolBoxICO.ico;." ^
  main.py

echo.
echo Build done. Output: dist\OYAToolBox\OYAToolBox.exe
pause
