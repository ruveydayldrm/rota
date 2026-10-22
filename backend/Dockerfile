# Hugging Face Spaces (port 7860, kullanıcı 1000) ve Render ile uyumlu.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=7860 \
    CACHE_PATH=/data/rota_cache.sqlite3

RUN useradd -m -u 1000 app && mkdir -p /data && chown app /data
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
USER app

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
