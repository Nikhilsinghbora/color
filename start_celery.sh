#!/bin/bash
# Start Celery worker and beat for local development
# Run this in a separate terminal while run_local.py is running

echo "Starting Celery services..."
echo ""

# Start Celery worker in background
uv run celery -A app.celery_app worker --loglevel=info --queues=game,wallet,email,reports,maintenance,analytics &
WORKER_PID=$!
echo "✓ Celery worker started (PID: $WORKER_PID)"

# Start Celery beat in background
uv run celery -A app.celery_app beat --loglevel=info &
BEAT_PID=$!
echo "✓ Celery beat started (PID: $BEAT_PID)"

echo ""
echo "Celery services running. Press Ctrl+C to stop..."
echo ""

# Trap Ctrl+C and kill background processes
trap "kill $WORKER_PID $BEAT_PID 2>/dev/null; exit" INT TERM

# Wait for processes
wait
