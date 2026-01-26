# Use Python 3.13 (stable, compatible with Django 5.x)
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=estimate_site.settings

# Set work directory
WORKDIR /app

# Install system dependencies including OCR support and curl for healthchecks
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
# Copy requirements first for better Docker layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p /app/logs /app/media /app/staticfiles /app/backups

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Health check - disabled for Railway (they have their own)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/health/ || exit 1

# Expose port
EXPOSE 8000

# Run with gunicorn - use shell form for variable expansion
CMD ["/bin/sh", "-c", "gunicorn estimate_site.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 300"]
