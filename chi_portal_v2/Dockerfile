FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8080

EXPOSE 8080

CMD ["gunicorn", "--timeout", "120", "--graceful-timeout", "30", "--workers", "2", "--max-requests", "500", "--max-requests-jitter", "50", "--bind", "0.0.0.0:8080", "app:app"]
