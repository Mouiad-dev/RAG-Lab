# RAG Lab — web (Django) image.
# Pinned base so the build is reproducible everywhere (plan: pin versions).
FROM python:3.13-slim

# Faster, quieter Python in containers.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first (own layer) so code edits don't re-run pip every build.
# psycopg[binary] bundles libpq, so no apt packages are needed yet.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY . .

# Django dev server. Host 0.0.0.0 so it's reachable from outside the container.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
