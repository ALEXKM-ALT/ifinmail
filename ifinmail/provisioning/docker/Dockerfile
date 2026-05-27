# ifinmail API container
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements/base.txt requirements/base.txt
COPY requirements/production.txt requirements/production.txt
RUN pip install --no-cache-dir --retries 5 -r requirements/production.txt

# Copy application code
COPY . .

# Collect static files
RUN mkdir -p /app/staticfiles && chown -R nobody:nogroup /app/staticfiles

COPY provisioning/docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN useradd -m -u 1000 -s /bin/bash app && \
    chown -R app:app /app

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "backend.config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", "--graceful-timeout", "60", "--keep-alive", "5", "--access-logfile", "-", "--error-logfile", "-"]
