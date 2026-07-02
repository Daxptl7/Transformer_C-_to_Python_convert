FROM python:3.11-slim

# Keep Python logs visible in Docker and avoid writing .pyc files in containers.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies if needed (e.g., git/curl for Hugging Face)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download the model and tokenizer to bake them into the Docker image layers.
# This makes container startup extremely fast and reliable.
RUN python -c "from transformers import AutoModelForSeq2SeqLM, AutoTokenizer; AutoTokenizer.from_pretrained('Salesforce/codet5-small'); AutoModelForSeq2SeqLM.from_pretrained('Salesforce/codet5-small')"

# Copy the rest of the application
COPY backend ./backend
COPY frontend ./frontend

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Run the startup script
CMD ["/app/start.sh"]
