#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then echo "Run as root" >&2; exit 1; fi

DEFAULT_APP_REPO_URL="https://github.com/synapticloop/digitalocean-wireguard-vpn.git"
DEFAULT_APP_REPO_BRANCH="main"

is_ipv4() {
  [[ "$1" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]
}

detect_external_ipv4() {
  local detected=""
  if command -v curl >/dev/null 2>&1; then
    detected="$(curl -fsS --connect-timeout 2 --max-time 5 http://169.254.169.254/metadata/v1/interfaces/public/0/ipv4/address 2>/dev/null || true)"
    if is_ipv4 "$detected"; then printf '%s\n' "$detected"; return 0; fi
    detected="$(curl -fsS --connect-timeout 2 --max-time 5 https://api.ipify.org 2>/dev/null || true)"
    if is_ipv4 "$detected"; then printf '%s\n' "$detected"; return 0; fi
  fi
  detected="$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i=="src") {print $(i+1); exit}}' || true)"
  if is_ipv4 "$detected"; then printf '%s\n' "$detected"; return 0; fi
  return 1
}

prompt_optional() {
  local var_name="$1"
  local prompt="$2"
  local default_value="$3"
  local current="${!var_name:-}"
  if [[ -n "$current" ]]; then return 0; fi
  if [[ -t 0 ]]; then
    read -rp "$prompt" current || true
    printf -v "$var_name" '%s' "${current:-$default_value}"
  else
    printf -v "$var_name" '%s' "$default_value"
  fi
}

DEFAULT_WG_ADMIN_DOMAIN="${WG_ADMIN_DOMAIN:-}"
if [[ -z "$DEFAULT_WG_ADMIN_DOMAIN" ]]; then
  DEFAULT_WG_ADMIN_DOMAIN="$(detect_external_ipv4 || true)"
fi
if [[ -z "${WG_ADMIN_DOMAIN:-}" && -z "$DEFAULT_WG_ADMIN_DOMAIN" ]]; then
  echo "WG_ADMIN_DOMAIN is not set and the installer could not detect an external IPv4 address." >&2
  echo "Set WG_ADMIN_DOMAIN=wg.example.com or WG_ADMIN_DOMAIN=<server-public-ip> and rerun the installer." >&2
  exit 1
fi

prompt_optional WG_ADMIN_DOMAIN "Admin domain or public IP [${DEFAULT_WG_ADMIN_DOMAIN}]: " "$DEFAULT_WG_ADMIN_DOMAIN"
prompt_optional APP_REPO_URL "Git repository URL [${DEFAULT_APP_REPO_URL}]: " "$DEFAULT_APP_REPO_URL"
prompt_optional APP_REPO_BRANCH "Git branch [${DEFAULT_APP_REPO_BRANCH}]: " "$DEFAULT_APP_REPO_BRANCH"
prompt_optional DIGITALOCEAN_API_TOKEN "DigitalOcean API token (optional, blank to skip): " ""
prompt_optional DIGITALOCEAN_DROPLET_ID "DigitalOcean droplet ID (optional, blank to skip): " ""
APP_DIR=/opt/wg-admin
APP_USER=wgadmin
WG_INTERFACE=wg0
WG_SERVER_IP=10.44.0.1
WG_LISTEN_PORT=51820
WG_PUBLIC_ENDPOINT="${WG_ADMIN_DOMAIN}:51820"
WG_CANDIDATE_PATH=/run/wg-admin/wg0.candidate.conf
WG_APP_DATA_DIR=/var/lib/wg-admin
PUBLIC_IFACE=$(ip route get 1.1.1.1 | awk '{for(i=1;i<=NF;i++) if ($i=="dev") {print $(i+1); exit}}')
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y wireguard wireguard-tools python3 python3-venv python3-pip git nginx certbot ufw sqlite3 curl dnsutils qrencode openssl
# Disable Ubuntu telemetry/crash reporting where present.
if command -v ubuntu-report >/dev/null 2>&1; then ubuntu-report -f send no || true; fi
systemctl disable --now apport.service 2>/dev/null || true
systemctl disable --now whoopsie.service 2>/dev/null || true
apt-get purge -y ubuntu-report popularity-contest apport whoopsie apport-symptoms || true
apt-mark hold ubuntu-report popularity-contest apport whoopsie apport-symptoms || true
id -u "$APP_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"
mkdir -p "$APP_DIR" "$WG_APP_DATA_DIR" /run/wg-admin /etc/wireguard
chown -R "$APP_USER:$APP_USER" "$APP_DIR" "$WG_APP_DATA_DIR" /run/wg-admin
chmod 700 /run/wg-admin
chmod 700 /etc/wireguard
if [[ ! -d "$APP_DIR/.git" ]]; then
  sudo -u "$APP_USER" git clone --branch "$APP_REPO_BRANCH" "$APP_REPO_URL" "$APP_DIR"
else
  sudo -u "$APP_USER" git -C "$APP_DIR" fetch origin
  sudo -u "$APP_USER" git -C "$APP_DIR" checkout "$APP_REPO_BRANCH"
  sudo -u "$APP_USER" git -C "$APP_DIR" pull --ff-only
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
python3 - <<'PY' > /tmp/wg_fernet_key
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
PY
FERNET_KEY=$(cat /tmp/wg_fernet_key)
DJANGO_SECRET_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(64))
PY
)
cat > "$APP_DIR/.env" <<ENVFILE
DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${WG_ADMIN_DOMAIN},${WG_SERVER_IP}
WG_ADMIN_DOMAIN=${WG_ADMIN_DOMAIN}
WG_INTERFACE=${WG_INTERFACE}
WG_SUBNET=10.44.0.0/24
WG_SERVER_IP=${WG_SERVER_IP}
WG_LISTEN_PORT=${WG_LISTEN_PORT}
WG_PUBLIC_ENDPOINT=${WG_PUBLIC_ENDPOINT}
WG_PUBLIC_INTERFACE=${PUBLIC_IFACE}
WG_CONFIG_PATH=/etc/wireguard/wg0.conf
WG_CANDIDATE_PATH=${WG_CANDIDATE_PATH}
WG_APP_DATA_DIR=${WG_APP_DATA_DIR}
WG_SQLITE_PATH=${WG_APP_DATA_DIR}/db.sqlite3
DJANGO_STATIC_ROOT=${WG_APP_DATA_DIR}/staticfiles
WG_ENCRYPTION_KEY=${FERNET_KEY}
ENVFILE
chown "$APP_USER:$APP_USER" "$APP_DIR/.env"; chmod 600 "$APP_DIR/.env"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" makemigrations --noinput
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
SERVER_PRIVATE=$(wg genkey); SERVER_PUBLIC=$(printf '%s' "$SERVER_PRIVATE" | wg pubkey)
ADMIN_PRIVATE=$(wg genkey); ADMIN_PUBLIC=$(printf '%s' "$ADMIN_PRIVATE" | wg pubkey)
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" shell <<PY
from accounts.models import User
from commits.models import ServerConfig
from peers.models import Peer
from usage.services import current_utc_month_period
from peers.services import build_client_config
from integrations.models import PrivacySettings
u, _ = User.objects.get_or_create(username='admin', defaults={'is_active': True, 'is_vpn_admin': True, 'email': ''})
u.is_active=True; u.is_vpn_admin=True; u.save()
ServerConfig.objects.all().delete(); ServerConfig.objects.create(private_key='${SERVER_PRIVATE}', public_key='${SERVER_PUBLIC}', listen_port=${WG_LISTEN_PORT})
Peer.objects.update_or_create(user=u, name='bootstrap-admin', defaults={'public_key':'${ADMIN_PUBLIC}', 'vpn_ipv4':'10.44.0.2', 'enabled':True})
PrivacySettings.get_solo()
current_utc_month_period()
PY
cat > /root/wg-admin-first-client.conf <<CLIENTCONF
[Interface]
PrivateKey = ${ADMIN_PRIVATE}
Address = 10.44.0.2/32
DNS = 9.9.9.9, 149.112.112.112

[Peer]
PublicKey = ${SERVER_PUBLIC}
Endpoint = ${WG_PUBLIC_ENDPOINT}
AllowedIPs = 0.0.0.0/0
PersistentKeepalive = 25
CLIENTCONF
chmod 600 /root/wg-admin-first-client.conf
qrencode -t ansiutf8 < /root/wg-admin-first-client.conf
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" shell -c "from commits.services import write_candidate; print(write_candidate())"
install -m 600 -o root -g root "$WG_CANDIDATE_PATH" /etc/wireguard/wg0.conf
cat > /etc/sysctl.d/99-wg-admin.conf <<SYSCTL
net.ipv4.ip_forward=1
SYSCTL
sysctl --system
cp /etc/ufw/before.rules /etc/ufw/before.rules.wg-admin.bak || true
if ! grep -q "WG-ADMIN NAT" /etc/ufw/before.rules; then
  UFW_BEFORE_TMP="$(mktemp)"
  cat > "$UFW_BEFORE_TMP" <<UFW_NAT
# WG-ADMIN NAT
*nat
:POSTROUTING ACCEPT [0:0]
-A POSTROUTING -s 10.44.0.0/24 -o ${PUBLIC_IFACE} -j MASQUERADE
COMMIT
# END WG-ADMIN NAT
UFW_NAT
  cat /etc/ufw/before.rules >> "$UFW_BEFORE_TMP"
  install -m 640 -o root -g root "$UFW_BEFORE_TMP" /etc/ufw/before.rules
  rm -f "$UFW_BEFORE_TMP"
fi
sed -i 's/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
ufw --force reset; ufw default deny incoming; ufw default allow outgoing
ufw allow ${WG_LISTEN_PORT}/udp
ufw allow in on ${WG_INTERFACE} to any port 443 proto tcp
ufw allow in on ${WG_INTERFACE} to any port 22 proto tcp
ufw --force enable
systemctl enable --now wg-quick@${WG_INTERFACE}
ufw allow 80/tcp comment 'temporary certbot http-01'
certbot certonly --standalone --preferred-challenges http -d "$WG_ADMIN_DOMAIN" --agree-tos --register-unsafely-without-email || true
ufw delete allow 80/tcp || true
if [[ ! -s "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}/fullchain.pem" || ! -s "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}/privkey.pem" ]]; then
  mkdir -p "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}"
  if is_ipv4 "$WG_ADMIN_DOMAIN"; then
    CERT_SAN="IP:${WG_ADMIN_DOMAIN}"
  else
    CERT_SAN="DNS:${WG_ADMIN_DOMAIN}"
  fi
  openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}/privkey.pem" \
    -out "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}/fullchain.pem" \
    -subj "/CN=${WG_ADMIN_DOMAIN}" \
    -addext "subjectAltName=${CERT_SAN}"
  chmod 600 "/etc/letsencrypt/live/${WG_ADMIN_DOMAIN}/privkey.pem"
fi
install -m 755 "$APP_DIR/scripts/wg-admin-commit" /usr/local/sbin/wg-admin-commit
install -m 755 "$APP_DIR/scripts/certbot-renew-http01.sh" /usr/local/sbin/wg-admin-certbot-renew
cat > /etc/sudoers.d/wg-admin <<SUDOERS
${APP_USER} ALL=(root) NOPASSWD: /usr/local/sbin/wg-admin-commit
SUDOERS
chmod 440 /etc/sudoers.d/wg-admin
cp "$APP_DIR/systemd/wg-admin.service" /etc/systemd/system/wg-admin.service
cp "$APP_DIR/systemd/wg-usage-collector.service" /etc/systemd/system/wg-usage-collector.service
cp "$APP_DIR/systemd/wg-usage-collector.timer" /etc/systemd/system/wg-usage-collector.timer
cp "$APP_DIR/nginx/wg-admin.conf" /etc/nginx/sites-available/wg-admin.conf
sed -i "s|__DOMAIN__|${WG_ADMIN_DOMAIN}|g; s|__WG_SERVER_IP__|${WG_SERVER_IP}|g" /etc/nginx/sites-available/wg-admin.conf
ln -sf /etc/nginx/sites-available/wg-admin.conf /etc/nginx/sites-enabled/wg-admin.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable --now wg-admin wg-usage-collector.timer
systemctl restart nginx
echo "Bootstrap complete. First admin config: /root/wg-admin-first-client.conf"
