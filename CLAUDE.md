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

**Status:** deployed to a real Pi and confirmed working, including the `/library` page
and its live cross-ZIM search (see the Architecture section below for how that's built,
and two non-obvious kiwix-serve deployment gotchas it took real hardware to surface).

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

Add content by dropping `.zim` files (from https://library.kiwix.org) into `content/zim/`,
then `sudo systemctl restart kiwix-serve`. `kiwix-serve` only accepts explicit ZIM file
paths or a `--library <xml>` file — it can't be pointed at a directory directly, so
`setup/kiwix-library-refresh.sh` runs as an `ExecStartPre` to regenerate
`content/library.xml` from whatever's in `content/zim/` each time the service (re)starts.
`--monitorLibrary` only watches that generated XML file for live-reload, not the `zim/`
directory itself, so newly dropped `.zim` files still need the restart above to be picked
up.

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

  `/library` (`app/routes.py`, `app/library.py`, `app/templates/library.html`) replaces
  kiwix-serve's own root welcome page, which is broken when proxied under `/kiwix/`
  (broken cover images, dead search links, a hardcoded kiwix.org link — none of that is
  our code, it's kiwix-serve's stock UI). It parses the kiwix-serve-generated
  `content/library.xml` (plain metadata via stdlib `ElementTree` — no new dependency, and
  `app/` still never opens ZIM files directly) to render a card per installed ZIM. Live
  search (`/api/search-suggest`, backed by `app/kiwix_client.py`) calls kiwix-serve's own
  `/suggest` endpoint directly on `127.0.0.1:<KIWIX_PORT><KIWIX_URL_ROOT>` once per
  installed ZIM — bypassing nginx/the browser entirely — and caps results per ZIM via
  `RESULTS_PER_ZIM` so one large ZIM (e.g. a full Wikipedia dump) can't flood out results
  from smaller ones. Card/article links are built from
  `KIWIX_VIEWER_URL_TEMPLATE`/`KIWIX_ARTICLE_URL_TEMPLATE`.

  **kiwix-serve must be told its own sub-path, or its self-generated links 404.** This bit
  real hardware: kiwix-serve (both its stock welcome page originally, and this app's first
  cut of `/library`) generates absolute in-page links like `/content/<book>` assuming it's
  mounted at the true root `/`. Proxied under `/kiwix/` with the prefix stripped (the
  original nginx config), those links 404 the moment you click into a book. The fix is
  kiwix-serve's own `-r`/`--urlRootLocation` flag: `setup/systemd/kiwix-serve.service`
  starts it with `--urlRootLocation /kiwix`, and `setup/nginx/rachel.conf`'s `/kiwix/`
  location proxies with **no trailing slash** on `proxy_pass` (so nginx forwards the full
  `/kiwix/...` path instead of stripping it) — the two must agree. `KIWIX_URL_ROOT` in
  `app/app.py`/`config/settings.env` mirrors the same value so Flask's direct
  server-to-server calls to kiwix-serve (bypassing nginx) hit the right path too. If you
  ever change the mount path, update all three in lockstep: the systemd unit's
  `--urlRootLocation`, the nginx location block, and `KIWIX_URL_ROOT`.

  **Book identifiers come from the ZIM filename, not `library.xml`'s `name` attribute.**
  Also confirmed on real hardware: kiwix-serve routes `/content`, `/suggest`, `/viewer`
  etc. by the ZIM's filename stem (e.g. `wikipedia_en_all_mini_2026-06`), which can differ
  from `library.xml`'s `name` metadata attribute (e.g. `wikipedia_en_all` — the same book
  without its flavour/date suffix). `app/library.py`'s `_parse_book` builds each `Book`'s
  identifier from `Path(path).stem` first, falling back to `name`/`id` only if `path` is
  missing — don't swap that priority back, it was the second real bug found after the
  `urlRootLocation` fix above (the first made links stop 404ing; this one made them point
  at the right book).

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
