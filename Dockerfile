# Pactiva Kurumsal Üretim İmajı (Dockerfile)
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Final Minimal İmaj
FROM python:3.12-slim

WORKDIR /app

# Güvenlik: Ayrıcalıksız sistem kullanıcısı
RUN groupadd -g 1000 pactiva && \
    useradd -u 1000 -g pactiva -s /bin/bash -m pactiva

COPY --from=builder /install /usr/local

COPY pactiva_core ./pactiva_core
COPY web ./web
COPY assets ./assets
COPY pactiva .

RUN chown -R pactiva:pactiva /app

USER pactiva

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health').getcode() == 200 else 1)"

CMD ["python3", "-m", "uvicorn", "pactiva_core.api:app", "--host", "0.0.0.0", "--port", "8000"]
