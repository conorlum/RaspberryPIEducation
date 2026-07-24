#!/usr/bin/env bash
# Configures this Pi to broadcast its own WiFi hotspot via NetworkManager,
# and makes every DNS query on that hotspot resolve back to the Pi itself -
# the trick that makes phones/laptops auto-open a captive-portal browser.
set -euo pipefail

if ! command -v nmcli >/dev/null; then
  echo "nmcli not found - this script requires NetworkManager (Raspberry Pi OS Bookworm+)." >&2
  exit 1
fi

: "${WIFI_SSID:?WIFI_SSID must be set (see config/settings.env)}"

WIFI_IFACE="${WIFI_IFACE:-wlan0}"
CONNECTION_NAME="rachel-hotspot"

if nmcli connection show "$CONNECTION_NAME" >/dev/null 2>&1; then
  nmcli connection delete "$CONNECTION_NAME"
fi

# Open network (no WIFI_PASSWORD) - temporary, revisit before final deployment.
nmcli connection add \
  type wifi \
  ifname "$WIFI_IFACE" \
  con-name "$CONNECTION_NAME" \
  autoconnect yes \
  ssid "$WIFI_SSID" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  ipv4.method shared

# NetworkManager runs its own dnsmasq instance for shared connections
# (default gateway/DNS on that interface is 10.42.0.1). Wildcarding every
# domain to that address is what makes a connecting device's captive-portal
# probe resolve to us instead of the real internet.
mkdir -p /etc/NetworkManager/dnsmasq-shared.d
cat > /etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf <<EOF
address=/#/10.42.0.1
EOF

nmcli connection up "$CONNECTION_NAME"

echo "Hotspot '$WIFI_SSID' is up on $WIFI_IFACE."
