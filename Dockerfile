FROM python:3.12-slim

# Don't buffer stdout (so logs appear immediately) and don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Install only what the smoke test needs for now. We keep this tiny on purpose;
# the real requirements.txt grows as we add Django, pgvector client, etc.
RUN pip install --no-cache-dir "psycopg[binary]==3.2.3" "httpx==0.27.2" "pyyaml==6.0.2"

COPY . /app

# On boot, run the smoke test. When Django arrives, this becomes runserver.
CMD ["python", "boot_check.py"]