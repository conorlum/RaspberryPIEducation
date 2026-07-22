#!/usr/bin/env bash
# Idempotent installer - run this on any Raspberry Pi 4 Model B with
# NetworkManager-based networking (Raspberry Pi OS Bookworm+, or plain
# Debian - the real deployed Pi runs Debian 13) to stand up the full stack:
# nginx, the Flask portal, kiwix-serve, and the WiFi hotspot. Safe to re-run
# after a `git pull` to pick up changes.
#
#   git clone <repo-url> && cd RaspberryPI
#   cp config/settings.example.env config/settings.env   # edit SSID/password
#   sudo ./setup/install.sh
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo: sudo ./setup/install.sh" >&2
  exit 1
fi

if ! command -v nmcli >/dev/null; then
  echo "nmcli not found - this installer requires NetworkManager (Raspberry Pi OS Bookworm+ or Debian with NetworkManager)." >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
APP_USER="${SUDO_USER:-$USER}"

echo "==> Installing system packages"
apt-get update
apt-get install -y nginx kiwix-tools python3-venv python3-pip

if [ ! -f "$APP_DIR/config/settings.env" ]; then
  echo "==> No config/settings.env found, creating one from the example"
  echo "    Edit it (SSID/password) before relying on the hotspot."
  cp "$APP_DIR/config/settings.example.env" "$APP_DIR/config/settings.env"
  chown "$APP_USER" "$APP_DIR/config/settings.env"
fi

echo "==> Setting up the Python virtualenv"
if [ ! -d "$APP_DIR/.venv" ]; then
  sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
fi
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "==> Installing systemd services"
for unit in rachel-portal kiwix-serve; do
  sed \
    -e "s|@APP_DIR@|$APP_DIR|g" \
    -e "s|@APP_USER@|$APP_USER|g" \
    "$SCRIPT_DIR/systemd/$unit.service" > "/etc/systemd/system/$unit.service"
done

echo "==> Installing nginx config"
cp "$SCRIPT_DIR/nginx/rachel.conf" /etc/nginx/sites-available/rachel.conf
ln -sf /etc/nginx/sites-available/rachel.conf /etc/nginx/sites-enabled/rachel.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t

echo "==> Configuring the WiFi hotspot"
set -a
# shellcheck disable=SC1091
source "$APP_DIR/config/settings.env"
set +a
"$SCRIPT_DIR/hotspot.sh"

echo "==> Hardening for offline / power-loss-prone deployment"
"$SCRIPT_DIR/harden-for-offline.sh"

echo "==> Starting services"
systemctl daemon-reload
systemctl enable --now rachel-portal kiwix-serve nginx
systemctl reload nginx

echo
echo "Done. Hotspot '${WIFI_SSID:-<unset>}' should be broadcasting."
echo "Check status with: systemctl status rachel-portal kiwix-serve nginx"
echo "Add content by copying .zim files into $APP_DIR/content/zim/, then run:"
echo "  sudo systemctl restart kiwix-serve"
