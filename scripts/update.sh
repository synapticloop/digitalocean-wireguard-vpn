#!/usr/bin/env bash
set -euo pipefail
APP_DIR=${APP_DIR:-/opt/wg-admin}
APP_USER=${APP_USER:-wgadmin}
BRANCH=${BRANCH:-main}
git -C "$APP_DIR" fetch origin
git -C "$APP_DIR" checkout "$BRANCH"
git -C "$APP_DIR" pull --ff-only
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" migrate
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" "$APP_DIR/manage.py" collectstatic --noinput
systemctl restart wg-admin
systemctl reload nginx
