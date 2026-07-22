@echo off
setlocal
cd /d "%~dp0"

if exist "D:\Myanaconda\python.exe" (
  "D:\Myanaconda\python.exe" run_local_collector.py
) else (
  python run_local_collector.py
)

if errorlevel 1 pause
