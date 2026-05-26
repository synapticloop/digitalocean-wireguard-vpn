#!/usr/bin/env bash
set -euo pipefail

# Remote installer for synapticloop/digitalocean-wireguard-vpn.
# Intended usage:
#   curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo bash
# Or non-interactive/minimal-prompt:
#   curl -fsSL https://raw.githubusercontent.com/synapticloop/digitalocean-wireguard-vpn/main/install.sh | sudo WG_ADMIN_DOMAIN=wg.example.com bash

DEFAULT_REPO_URL="https://github.com/synapticloop/digitalocean-wireguard-vpn.git"
DEFAULT_BRANCH="main"
APP_REPO_URL="${APP_REPO_URL:-$DEFAULT_REPO_URL}"
APP_REPO_BRANCH="${APP_REPO_BRANCH:-$DEFAULT_BRANCH}"

if [[ ${EUID} -ne 0 ]]; then
  echo "This installer must be run as root. Use: curl -fsSL <url> | sudo bash" >&2
  exit 1
fi

if [[ -r /etc/os-release ]]; then
  . /etc/os-release
  if [[ "${ID:-}" != "ubuntu" || "${VERSION_ID:-}" != "24.04" ]]; then
    echo "WARNING: this installer targets Ubuntu 24.04 LTS. Detected: ${PRETTY_NAME:-unknown}." >&2
    if [[ -t 0 ]]; then
      read -rp "Continue anyway? [y/N]: " CONTINUE
      [[ "$CONTINUE" =~ ^[Yy]$ ]] || exit 1
    else
      echo "Set WG_ADMIN_FORCE_UNSUPPORTED_OS=1 to bypass this check in non-interactive mode." >&2
      [[ "${WG_ADMIN_FORCE_UNSUPPORTED_OS:-}" == "1" ]] || exit 1
    fi
  fi
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl git gnupg lsb-release

WORKDIR=$(mktemp -d /tmp/wg-admin-install.XXXXXX)
cleanup() { rm -rf "$WORKDIR"; }
trap cleanup EXIT

echo "Cloning ${APP_REPO_URL} (${APP_REPO_BRANCH})..."
git clone --depth 1 --branch "$APP_REPO_BRANCH" "$APP_REPO_URL" "$WORKDIR/repo"

chmod +x "$WORKDIR/repo/scripts/bootstrap_ubuntu_2404.sh"
export APP_REPO_URL APP_REPO_BRANCH
exec "$WORKDIR/repo/scripts/bootstrap_ubuntu_2404.sh"
