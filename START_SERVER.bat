@echo off
title PCB AI Inspection & Photometric 3D Studio
echo ===============================================================
echo   STARTING PCB AI INSPECTION & PHOTOMETRIC 3D STUDIO (PORT 8080)
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

echo Launching Web Server at http://localhost:8080 ...
start http://localhost:8080
start http://localhost:8080/photometric-studio
%PYTHON_CMD% -m uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload
pause

