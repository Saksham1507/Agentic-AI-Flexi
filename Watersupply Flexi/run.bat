@echo off
title WaterCare AI - Intelligent Complaint Management Agent
echo ================================================================
echo    Starting WaterCare AI - Intelligent Complaint Management Agent
echo ================================================================
echo.
echo Opening http://127.0.0.1:8000 ...
start http://127.0.0.1:8000
echo.
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
pause
