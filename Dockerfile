FROM python:3.11-slim
WORKDIR /app

# Optional: set at build time for /version (e.g. docker build --build-arg GIT_SHA=$(git rev-parse --short HEAD))
ARG GIT_SHA=unknown
ENV EDON_GIT_SHA=${GIT_SHA}
ENV GIT_SHA=${GIT_SHA}

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./edon_gateway/
ENV PYTHONPATH=/app

# Persisted data (mount volume at /app/data)
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

CMD ["python", "-m", "uvicorn", "edon_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
