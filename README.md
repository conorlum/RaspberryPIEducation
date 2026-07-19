# RACHEL-Pi

An offline education server for Raspberry Pi, inspired by
[RACHEL](https://rachel.worldpossible.org/). The Pi broadcasts its own WiFi hotspot; any
device that connects gets a captive-portal popup straight into a library of offline content
(Wikipedia, Khan Academy, etc. via [Kiwix](https://www.kiwix.org/) ZIM files) — no internet
connection required.

## How it works

Three services on the Pi, fronted by nginx:

- **nginx** (`:80`) — routes WiFi captive-portal detection probes to Flask, proxies
  `/kiwix/*` to kiwix-serve, and sends everything else to Flask.
- **Flask app** (`app/`, via gunicorn on `:5000`) — the landing page, plus the
  captive-portal redirect logic that makes phones/laptops auto-open a browser on connect.
- **kiwix-serve** (`:8080`, from the `kiwix-tools` apt package) — serves whatever `.zim`
  files are placed in `content/zim/`: full-text search, browsable library, video playback.

A dnsmasq override (set up by `setup/hotspot.sh`) makes every DNS query on the hotspot
resolve to the Pi's own IP, which is what triggers phones/laptops to detect a captive
portal and pop the browser open automatically.

## Local development (this repo, on any machine)

```
python -m venv .venv
.venv\Scripts\activate        # or: source .venv/bin/activate on Linux/Mac
pip install -r requirements.txt
pytest
flask --app app.app run
```

Browse `http://localhost:5000` — the landing page renders even without kiwix-serve running;
content links just won't resolve until deployed to the Pi.

## Deploying to a Raspberry Pi

Target: Raspberry Pi 4 Model B running Raspberry Pi OS Bookworm (NetworkManager-based
networking). On the Pi:

```
git clone <this-repo-url>
cd RaspberryPI
cp config/settings.example.env config/settings.env   # edit SSID/password
sudo ./setup/install.sh
```

`install.sh` is idempotent — installs system packages (nginx, kiwix-tools, python3-venv),
sets up the Python venv, installs the systemd services and nginx config, configures the
WiFi hotspot, and starts everything. Run the same steps on any additional Pi to replicate
the setup.

Add offline content by copying `.zim` files into `content/zim/` (get them from
https://library.kiwix.org) and restarting `kiwix-serve`:

```
sudo systemctl restart kiwix-serve
```

## Repo layout

- `app/` — the Flask portal (landing page + captive-portal routes)
- `content/zim/` — ZIM files served by kiwix-serve (not checked into git — too large)
- `setup/` — nginx config, systemd units, the WiFi hotspot script, and `install.sh`
- `config/` — per-deployment settings (`settings.env`, gitignored; see
  `settings.example.env` for the template)
- `tests/` — pytest route tests, runnable without a Pi
