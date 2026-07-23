#!/usr/bin/env bash
# Hardens this Pi for its actual deployment conditions: no internet access
# ever (once it leaves this network), and power that can cut out without
# warning. None of this is optional per-deployment config - every Pi this
# project gets installed on faces the same two conditions, so it belongs in
# the shared install flow rather than a one-off manual fix.
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo (it's called from install.sh, which already does)." >&2
  exit 1
fi

echo "==> Disabling boot-time services that depend on internet access this Pi will never have"
# These can only ever fail or time out once this Pi is off this network -
# disabling them shaves real time off every power-loss recovery boot and
# removes any chance of them hanging while they wait for connectivity that
# will never arrive. --now also stops the currently-running instance.
systemctl disable --now NetworkManager-wait-online.service 2>/dev/null || true
systemctl disable --now apt-daily.timer apt-daily-upgrade.timer 2>/dev/null || true
systemctl disable --now apt-daily.service apt-daily-upgrade.service 2>/dev/null || true

if command -v cloud-init >/dev/null 2>&1; then
  echo "==> Disabling cloud-init (its one-time provisioning is already done)"
  touch /etc/cloud/cloud-init.disabled
  systemctl disable cloud-init cloud-init-local cloud-config cloud-final 2>/dev/null || true
fi

echo "==> Installing fake-hwclock"
# There's no RTC on this hardware, so without this, a power-loss reboot
# with no internet (no NTP) leaves the system clock reset to whatever the
# kernel defaults to. fake-hwclock persists the time across reboots as a
# best-effort guess instead. Must be installed now, while there's still
# internet to install it with - it can't be added later at the deployment
# site.
apt-get install -y fake-hwclock

echo "==> Capping journald's on-disk log size"
# Reduces SD card write volume (and the corruption window during a power
# cut) with no functional downside for a box nobody's routinely reading
# historical logs from.
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/offline-limit.conf <<'EOF'
[Journal]
SystemMaxUse=50M
EOF
systemctl restart systemd-journald

echo "Offline/power-loss hardening complete."
