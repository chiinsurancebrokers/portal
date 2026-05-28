FROM python:3.11-slim

WORKDIR /app

# System dependencies for psycopg2, PyMuPDF, pdfplumber
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

EXPOSE $PORT

CMD gunicorn --timeout 120 --workers 2 --bind 0.0.0.0:$PORT app:app
