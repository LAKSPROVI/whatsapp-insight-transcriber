FROM python:3.12-slim

WORKDIR /app

# Instalar dependências do sistema (ffmpeg para processamento de vídeo/áudio)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretórios
RUN mkdir -p /app/data/uploads /app/data/media

# Criar usuário não-root
RUN adduser --system --uid 1001 appuser && \
    chown -R appuser:nogroup /app /app/data

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=15s --timeout=10s --start-period=30s --retries=8 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Iniciar servidor (rodar como root para garantir acesso ao volume, então drop para appuser)
CMD ["sh", "-c", "chown -R appuser:nogroup /app/data 2>/dev/null; exec su -s /bin/sh appuser -c 'uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1'"]
