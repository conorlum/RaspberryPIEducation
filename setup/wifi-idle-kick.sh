#!/usr/bin/env bash
# Kicks WiFi clients that have gone idle, but only when the hotspot is
# close to its known hardware ceiling. The onboard chip on this Pi 4 has
# been confirmed (real thermal/concurrency testing) to reliably support
# only ~15-20 concurrent associated stations in AP mode before it starts
# dropping or refusing connections. The hotspot is currently an open
# network (see setup/hotspot.sh), so nothing stops it filling up with
# idle-but-still-associated devices - a phone left in a bag, a laptop lid
# closed - quietly starving a student who's trying to connect. This uses
# the generic nl80211 station commands (`iw ... station dump` / `station
# del`), not hostapd_cli: NetworkManager's own AP mode has no hostapd
# process behind it in this deployment (see CLAUDE.md), so there is no
# hostapd control socket to talk to here.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run this as root (it's called from systemd, which already does)." >&2
  exit 1
fi

if ! command -v iw >/dev/null; then
  echo "iw not found - required to inspect/kick WiFi stations." >&2
  exit 1
fi

WIFI_IFACE="${WIFI_IFACE:-wlan0}"

# Below this many associated stations there's no real capacity pressure -
# leave everyone connected no matter how long they've been idle. Chosen
# with headroom under the *low* end of the ~15-20 station hardware ceiling
# (confirmed via real testing) rather than the high end, since a device
# that's idle below this count costs nothing by staying connected.
STATION_TRIGGER=10

# How long a station can go without sending or receiving a single 802.11
# frame before it's considered idle enough to sacrifice for a new
# connection. This is link-layer activity (any frame at all), so a device
# actively streaming video or browsing/searching keeps resetting this - it
# only trips for something that has gone genuinely silent at the radio
# level. 15 minutes comfortably exceeds a plausible silent-reading pause on
# a single static page without camping a slot for most of a class period.
IDLE_THRESHOLD_MS=900000

if ! ip link show "$WIFI_IFACE" >/dev/null 2>&1; then
  echo "Interface $WIFI_IFACE not found, skipping this run." >&2
  exit 0
fi

# station dump can legitimately be empty (no clients) or transiently fail
# (interface mid-restart) - neither is an error worth failing the unit
# over, the next timer tick just tries again.
dump="$(iw dev "$WIFI_IFACE" station dump 2>/dev/null || true)"

station_count="$(printf '%s\n' "$dump" | grep -c '^Station' || true)"

if [ "$station_count" -lt "$STATION_TRIGGER" ]; then
  echo "==> $station_count station(s) associated on $WIFI_IFACE (below trigger of $STATION_TRIGGER) - nothing to do"
  exit 0
fi

echo "==> $station_count station(s) associated on $WIFI_IFACE (at/above trigger of $STATION_TRIGGER) - checking for idle stations to free up slots"

kicked=0
while read -r mac inactive_ms; do
  [ -z "$mac" ] && continue
  if [ "$inactive_ms" -ge "$IDLE_THRESHOLD_MS" ]; then
    echo "==> Kicking $mac (idle ${inactive_ms}ms >= ${IDLE_THRESHOLD_MS}ms threshold)"
    iw dev "$WIFI_IFACE" station del "$mac" 2>/dev/null \
      || echo "    (already gone by the time we tried - fine)" >&2
    kicked=$((kicked + 1))
  fi
done < <(printf '%s\n' "$dump" | awk '/^Station/ {mac=$2} /inactive time:/ {print mac, $3}')

echo "==> Done - kicked $kicked idle station(s)"
