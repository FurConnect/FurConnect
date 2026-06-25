# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        git \
        pkg-config \
        libcairo2-dev \
        git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . /app/

# Bake git version for runtime (git may be unavailable or blocked in container)
ARG FURCONNECT_GIT_HASH=
ARG FURCONNECT_GIT_DATE=
RUN if [ -n "$FURCONNECT_GIT_HASH" ] && [ -n "$FURCONNECT_GIT_DATE" ]; then \
        printf '%s\n%s\n' "$FURCONNECT_GIT_HASH" "$FURCONNECT_GIT_DATE" > /app/furconnect_version; \
    else \
        python -c "from FurConnectApp.version_info import write_version_file; write_version_file('/app')"; \
    fi

# Create directories for static and media files
RUN mkdir -p /app/staticfiles /app/media

# Collect static files
RUN python manage.py collectstatic --noinput

# Create a non-root user
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Run the application
CMD ["sh", "start.sh"]