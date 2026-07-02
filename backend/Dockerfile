# Backend image for the FastAPI + CodeT5 inference service.
FROM python:3.11-slim

# Keep Python logs visible in Docker and avoid writing .pyc files in containers.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies before copying source files so Docker can reuse the
# dependency layer when only application code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend ./backend

EXPOSE 8000

# The model is loaded during FastAPI startup by backend/fastapi_app.py.
CMD ["uvicorn", "backend.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
