# Frontend image for the Streamlit UI.
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

COPY frontend ./frontend

EXPOSE 8501

# Streamlit must listen on 0.0.0.0 so it is reachable from outside the container.
CMD [
    "streamlit",
    "run",
    "frontend/streamlit_app.py",
    "--server.address=0.0.0.0",
    "--server.port=8501"
]
