#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Script de Setup Inicial do Servidor Hetzner
# Execute UMA VEZ na primeira configuração do servidor
# Uso: bash scripts/setup-server.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

HETZNER_HOST="77.42.68.212"
HETZNER_USER="root"
SSH_KEY="$HOME/.ssh/hetzner_key"
APP_DIR="/opt/whatsapp-insight-transcriber"

echo "🚀 Configurando servidor Hetzner ($HETZNER_HOST)..."

ssh -i "$SSH_KEY" "$HETZNER_USER@$HETZNER_HOST" << 'REMOTE_SCRIPT'
set -e

echo "📦 Atualizando pacotes..."
apt-get update -y && apt-get upgrade -y

echo "🐳 Instalando Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    echo "✅ Docker instalado"
else
    echo "✅ Docker já instalado: $(docker --version)"
fi

echo "🔧 Instalando Docker Compose Plugin..."
apt-get install -y docker-compose-plugin
echo "✅ Docker Compose: $(docker compose version)"

echo "📁 Criando diretórios da aplicação..."
mkdir -p /opt/whatsapp-insight-transcriber/data/{uploads,media}

echo "🔥 Configurando firewall (UFW)..."
apt-get install -y ufw
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 3000/tcp
ufw allow 8000/tcp
ufw --force enable
echo "✅ Firewall configurado"

echo "📦 Instalando utilitários..."
apt-get install -y curl git rsync htop ffmpeg

echo "🔒 Configurando swap (2GB)..."
if [ ! -f /swapfile ]; then
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' | tee -a /etc/fstab
    echo "✅ Swap configurado"
fi

echo ""
echo "═══════════════════════════════════════════"
echo "✅ Servidor configurado com sucesso!"
echo "🐳 Docker: $(docker --version)"
echo "📦 Compose: $(docker compose version)"
echo "💾 Swap: $(free -h | grep Swap)"
echo "═══════════════════════════════════════════"
REMOTE_SCRIPT

echo ""
echo "✅ Setup do servidor Hetzner concluído!"
echo "🌐 Próximo passo: execute o deploy via GitHub Actions ou manualmente"
