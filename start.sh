#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting FastAPI backend on port 8000..."
uvicorn backend.fastapi_app:app --host 0.0.0.0 --port 8000 &

echo "Starting Streamlit frontend on port 7860..."
streamlit run frontend/streamlit_app.py --server.port 7860 --server.address 0.0.0.0
