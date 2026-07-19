# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A RACHEL-style (rachel.worldpossible.org) offline education server for Raspberry Pi. The
Pi broadcasts its own WiFi hotspot; connecting devices get a captive-portal popup into a
library of offline content (Wikipedia, Khan Academy, etc. via Kiwix ZIM files). No internet
required. Target hardware is a Raspberry Pi 4 Model B running Raspberry Pi OS Bookworm
(NetworkManager-based networking) — the WiFi hotspot setup depends on `nmcli` and will not
work on older Raspberry Pi OS releases that use dhcpcd/hostapd instead.

This repo is meant to be cloned onto multiple Pis via `setup/install.sh` to replicate the
same setup on each one — see "Deploying to a Pi" below.

## Commands

```
python -m venv .venv
.venv\Scripts\activate              # Windows; use `source .venv/bin/activate` on Linux/Mac
pip install -r requirements.txt

pytest                              # run the full test suite
pytest tests/test_routes.py::test_index_renders   # run a single test

flask --app app.app run             # local dev server at localhost:5000
```

Tests and the dev server run fine on any machine (Windows included) — only `setup/*.sh`
and the systemd/nginx/hotspot pieces require actual Pi/Linux hardware to exercise.

### Deploying to a Pi

```
git clone <repo-url> && cd RaspberryPI
cp config/settings.example.env config/settings.env   # edit SSID/password first
sudo ./setup/install.sh
```

`install.sh` is idempotent (safe to re-run after `git pull`). It installs apt packages
(nginx, kiwix-tools, python3-venv), builds the venv, installs the systemd units and nginx
config (substituting `@APP_DIR@`/`@APP_USER@` placeholders via `sed` so the same unit
templates work regardless of clone path), runs `setup/hotspot.sh`, and enables/starts all
three services. Re-running this same script on a second Pi is the "push to another Pi"
deployment path.

Add content by dropping `.zim` files (from https://library.kiwix.org) into `content/zim/`
— `kiwix-serve` runs with `--monitorLibrary` and picks them up without a restart.

## Architecture

Three services, fronted by nginx, deployed together by `install.sh`:

```
device on hotspot -> nginx :80 -> /kiwix/*  -> kiwix-serve :8080 (serves *.zim from content/zim/)
                                -> /* (else) -> Flask/gunicorn :5000 (app/)
```

- **kiwix-serve** owns all ZIM parsing, full-text search, the library browsing UI, and
  correct HTTP range-request handling for embedded video. It is not reimplemented in
  Python — `app/` never touches ZIM files directly.
- **nginx** (`setup/nginx/rachel.conf`) is the only thing that knows both backends exist;
  it proxies `/kiwix/` to kiwix-serve and everything else to Flask. It does not need any
  captive-portal-specific logic — see below for why.
- **Flask** (`app/`) is intentionally the small, hackable layer: the landing page
  (`app/routes.py` `index()`, `app/templates/index.html`) and the captive-portal redirect
  logic. This is the layer to extend for custom pages, branding, or additional content
  types — don't add ZIM/content-serving logic here; that belongs to kiwix-serve.

### Captive portal mechanism (the trickiest part — read before touching hotspot/routing code)

Two pieces work together to get phones/laptops to auto-popup a browser on connect,
matching the real RACHEL device's UX:

1. `setup/hotspot.sh` writes a dnsmasq override
   (`/etc/NetworkManager/dnsmasq-shared.d/captive-portal.conf`) that wildcards **every**
   DNS query on the hotspot to the Pi's own address (`10.42.0.1`, NetworkManager's default
   shared-mode gateway).
2. Because of that DNS override, each OS's connectivity-check request (Android
   `/generate_204`, Apple `/hotspot-detect.html`, Windows `/connecttest.txt` /
   `/ncsi.txt`, etc.) lands on the Pi instead of the real internet. `app/routes.py`
   registers those exact paths (`CAPTIVE_PORTAL_PROBES`) and 302-redirects all of them to
   `/`, which is what makes the OS treat this as a captive portal and auto-launch a
   browser straight to the landing page. A catch-all route (`catch_all`) does the same
   for any other unrecognized path, so nginx never needs its own captive-portal routing —
   it just needs to send non-`/kiwix/` traffic to Flask.

If you add a new probe path for another OS/browser, add it to `CAPTIVE_PORTAL_PROBES` in
`app/routes.py` rather than special-casing it in nginx.

### Config

`config/settings.env` (gitignored, per-deployment — template is
`config/settings.example.env`) holds `PORTAL_TITLE`, `WIFI_SSID`, `WIFI_PASSWORD`,
`KIWIX_PORT`, `PORTAL_PORT`. `app/app.py` loads it via `python-dotenv`;
`setup/hotspot.sh` and `install.sh` read it directly as shell env vars. This is what lets
the same code/systemd-unit templates be reused across Pis with different SSIDs.

### systemd units

`setup/systemd/*.service` are templates with `@APP_DIR@`/`@APP_USER@` placeholders — they
are not meant to be copied to `/etc/systemd/system/` directly; `install.sh` does the `sed`
substitution. If you change these templates, keep the placeholder names in sync with the
`sed` invocation in `install.sh`.
