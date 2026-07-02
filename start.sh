#!/bin/bash

set -u

export TRANSLATE_API_URL="${TRANSLATE_API_URL:-http://127.0.0.1:8000/translate}"

echo "Starting FastAPI backend on port 8000..."
uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

echo "Waiting for FastAPI health check..."
BACKEND_READY=false
for _ in {1..30}; do
    if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
        echo "FastAPI backend exited before becoming ready."
        break
    fi

    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
        BACKEND_READY=true
        echo "FastAPI backend is ready."
        break
    fi

    sleep 1
done

if [ "$BACKEND_READY" != "true" ]; then
    echo "Continuing with Streamlit; local translator fallback will be used if API calls fail."
fi

echo "Starting Streamlit frontend on port 7860..."
streamlit run frontend/streamlit_app.py --server.port 7860 --server.address 0.0.0.0
