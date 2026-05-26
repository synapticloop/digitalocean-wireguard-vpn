#!/usr/bin/env bash
set -euo pipefail
cleanup() { ufw delete allow 80/tcp >/dev/null 2>&1 || true; }
trap cleanup EXIT
ufw allow 80/tcp comment 'temporary certbot http-01'
certbot renew --standalone --preferred-challenges http
systemctl reload nginx || true
