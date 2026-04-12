FROM python:3.12-slim

# Dépendances système pour psycopg2, lxml, curl_cffi, etc.
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    libxml2-dev \
    libxslt-dev \
    libcurl4-openssl-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installer les dépendances Python en premier (layer cache)
COPY backend/requirements-backend.txt ./requirements-backend.txt
RUN pip install --no-cache-dir -r requirements-backend.txt

# Copier tout le projet (le backend importe depuis agents/, orchestrator/, db/, data/, etc.)
COPY . .

EXPOSE 8000

# --no-reload en prod, --skip-tests car déjà fait par CI
CMD ["python", "-m", "uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
