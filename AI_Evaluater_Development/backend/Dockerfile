FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV TORCH_HOME=/tmp/torch
ENV HF_HOME=/tmp/huggingface

# Install system dependencies
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get update -y && \
    apt-get install -y --no-install-recommends \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with CPU-only torch
RUN pip install --upgrade pip && \
    pip install --no-cache-dir \
    --index-url https://download.pytorch.org/whl/cpu \
    torch torchvision && \
    pip install --no-cache-dir -r requirements.txt && \
    # Clean up pip cache
    rm -rf /root/.cache/pip

# Copy application code (excluding unnecessary files)
COPY app.py config.py Procfile ./
COPY models/ ./models/
COPY utils/ ./utils/

# Create uploads directory
RUN mkdir -p uploads

# Remove unnecessary files
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -type f -name "*.pyc" -delete && \
    find . -type f -name "*.pyo" -delete

# Expose Hugging Face default port
EXPOSE 7860

# Run the application with gevent async workers (required for SSE streaming)
CMD ["gunicorn", "--bind", "0.0.0.0:7860", "--workers", "2", "--worker-class", "gevent", "--timeout", "900", "app:app"]
