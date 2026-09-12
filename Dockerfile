FROM python:3.12-slim

# Don't buffer stdout (so logs appear immediately) and don't write .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# External CLI tools the ingestion path shells out to (NOT pip packages):
#   tesseract-ocr + tesseract-ocr-ara -> OCR for image PDFs / manga (eng+ara)
#   poppler-utils                     -> pdftotext / pdftoppm (text-PDF fallback)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-ara poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Python deps from the manifest (single source of truth). Copy just the file
# first so this layer is cached and only reruns when requirements change.
# docling (requirements-ingest.txt) is intentionally NOT installed here — it's
# heavy and ingest-only; text_pdf falls back to the pdftotext CLI above.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

# On boot, run the smoke test. When Django arrives, this becomes runserver.
CMD ["python", "boot_check.py"]
