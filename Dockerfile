# Multi-stage Dockerfile para NFE Manager
# -----------------------------------------------------------
# Stage 1: Build & Dependencies
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    libxmlsec1-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt requirements.txt
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------
# Stage 2: Final Runtime Image
FROM python:3.12-slim AS runtime

WORKDIR /app

# Dependências de runtime do SO para NF-e (XML/SOAP, SSL, fontes de DANFE PDF)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 \
    libxslt1.1 \
    libxmlsec1-openssl \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cria usuário sem privilégios de root para segurança
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app appuser

# Copia pacotes Python instalados pelo builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONPATH=/app

# Copia o código da aplicação
COPY --chown=appuser:appgroup . /app

# Prepara diretórios com permissões adequadas
RUN mkdir -p /app/data /app/certs /app/data/xmls /app/data/backups && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
