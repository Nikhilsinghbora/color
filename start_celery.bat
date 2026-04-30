@echo off
REM Start Celery worker and beat for local development
REM Run this in a separate terminal window while run_local.py is running

echo Starting Celery services...
echo.

REM Start Celery worker in background
start "Celery Worker" cmd /k "uv run celery -A app.celery_app worker --loglevel=info --pool=solo --queues=game,wallet,email,reports,maintenance,analytics"

REM Wait a bit for worker to start
timeout /t 3 /nobreak >nul

REM Start Celery beat
start "Celery Beat" cmd /k "uv run celery -A app.celery_app beat --loglevel=info"

echo.
echo Celery services started in separate windows!
echo Press any key to exit this window...
pause >nul
