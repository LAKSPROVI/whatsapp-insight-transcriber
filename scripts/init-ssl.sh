#!/bin/sh
set -eu

DOMAIN="${APP_DOMAIN:-transcriber.jurislaw.com.br}"
EMAIL="${LETSENCRYPT_EMAIL:-admin@jurislaw.com.br}"
LIVE_DIR="/etc/letsencrypt/live/$DOMAIN"

echo "Waiting for bootstrap nginx on HTTP..."
i=0
until docker compose exec -T nginx wget --spider -q http://127.0.0.1/nginx-health; do
  i=$((i + 1))
  if [ "$i" -ge 30 ]; then
    echo "Nginx bootstrap did not become healthy in time" >&2
    exit 1
  fi
  sleep 2
done

if docker compose exec -T nginx test -f "$LIVE_DIR/fullchain.pem" \
  && docker compose exec -T nginx test -f "$LIVE_DIR/privkey.pem"; then
  echo "Certificate already exists, skipping issuance."
else
  echo "Requesting initial certificate for $DOMAIN..."
  docker compose run --rm certbot certonly \
    --non-interactive \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring \
    -d "$DOMAIN"
fi

echo "Activating HTTPS nginx config..."
docker compose exec -T nginx sh -eu -c '
  cp /etc/nginx/templates/nginx-https.conf /etc/nginx/conf.d/default.conf
  nginx -t
  nginx -s reload
'

echo "Initial SSL setup complete."
