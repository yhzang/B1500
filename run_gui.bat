@echo off
REM B1500 FeFET GUI launcher (ASCII only; CJK in a .bat breaks cmd parsing).
REM Location: D:\test\B1500\run_gui.bat  -- make a Desktop shortcut to double-click.
REM CLI is unaffected: still  python scripts\wgfmu_next_round_minimal.py
cd /d "%~dp0"
".venv\Scripts\python.exe" -m gui
if errorlevel 1 (
  echo.
  echo [start failed] Install GUI deps first, then retry:
  echo     .venv\Scripts\pip install -r requirements\gui.txt
  echo.
  pause
)
