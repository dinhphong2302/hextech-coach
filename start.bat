@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist config.json (
  copy config.example.json config.json >nul
  echo Da tao config.json. Mo file nay, dien API key roi chay lai start.bat.
  notepad config.json
  exit /b
)
REM Che do go loi: hien cua so den kem nhat ky
python main.py watch
pause
