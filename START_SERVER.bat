@echo off
title PCB AI Inspection & Photometric 3D Studio
echo ===============================================================
echo   STARTING INSPECTRA AOI COMMAND CENTER & DIGITAL TWIN (PORT 8000)
echo ===============================================================
echo.

set PYTHON_CMD=py -3.11
where py >nul 2>&1
if errorlevel 1 (
    if exist "C:\Users\kthir\Python311\python.exe" (
        set PYTHON_CMD="C:\Users\kthir\Python311\python.exe"
    ) else (
        set PYTHON_CMD=python
    )
)

echo Launching Web Server at http://localhost:8000 ...
start http://localhost:8000
%PYTHON_CMD% -m uvicorn server.main:app --host 127.0.0.1 --port 8000 --reload
pause

