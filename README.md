# LCD panel stats

A small two machine setup: the **server** exposes CPU temperature, NVIDIA GPU temperature, RAM use, and network speeds as JSON; the **client** polls it and rotates those values on a 16 × 2 character LCD attached to a Raspberry Pi.

## Requirements

- Server: Linux, Python 3.11 or newer, an NVIDIA GPU with a working driver (`nvidia-smi` should work), and network access from the Pi.
- Client: Raspberry Pi running Linux with Python 3.11 or newer, a supported GPIO setup, and a character LCD wired to the pins in `client/config.example.toml` (or edit the pins in `client/config.toml`).
- Both: [uv](https://docs.astral.sh/uv/getting-started/installation/), `git`, and `sudo` access to install a systemd service.

Clone the repository on **both** machines. Run the installer as the normal account that will run the service, from either machine's clone:

```bash
git clone https://github.com/albertodicaprio/lcd-panel-stats.git
cd lcd-panel-stats
python3 install.py server  # on the NVIDIA machine
python3 install.py client  # on the Raspberry Pi
```

The server installer asks for the HTTP port, GPU index, and CPU temperature sensor and labels; defaults match the original setup. The client installer asks for the server hostname or IP address and port. Each installer creates its role's ignored `config.toml`, runs `uv sync --locked`, writes a systemd unit under `/etc/systemd/system/`, and enables and starts it. It derives the service user's name and paths from the current account and clone location. Run `python3 install.py --dry-run server` or `python3 install.py --dry-run client` to inspect the config and unit before installation.

Start the server before the client. Ensure the server's chosen port is reachable from the Pi. Test it with `curl http://SERVER_HOST:5000/stats`. The server listens on all interfaces by default; set `bind_host` in `server/config.toml` if a different interface is needed. The HTTP endpoint has no authentication, so use it only on a trusted network or behind suitable network controls.

## Configuration

The installer keeps existing `config.toml` files when run again. Edit them to change settings, then restart the relevant service. The tracked example files describe every setting:

- `server/config.example.toml`: HTTP bind host and port, NVIDIA GPU index, CPU sensor name and preferred sensor labels. The default CPU sensor is `k10temp` with `Tccd1` then `Tctl`, matching the original AMD setup. For other CPUs, inspect the available names with `sensors` or `uv run --project server python -c 'import psutil; print(psutil.sensors_temperatures())'`.
- `client/config.example.toml`: server URL, request timeout, LCD dimensions and BCM pin numbers, and refresh interval. The default wiring is RS=26, E=19, data=25,24,22,27.

Configuration is read from the role's `config.toml` by default. For a temporary override, set `LCD_STATS_CONFIG` to an absolute TOML file path. Keep the client URL pointed at `/stats`.

## Service checks

```bash
systemctl status lcd-stats-server.service
systemctl status lcd-stats-client.service
journalctl -u lcd-stats-server.service -f
journalctl -u lcd-stats-client.service -f
```

Run these commands on the machine hosting the relevant role. After editing config, restart with `sudo systemctl restart lcd-stats-server.service` or `sudo systemctl restart lcd-stats-client.service`. Re-run `python3 install.py ROLE` after moving the clone or upgrading dependencies so uv and systemd use the new location.

To uninstall a service on its machine, run `python3 install.py remove server` or `python3 install.py remove client`. This stops and disables the service, removes its unit from `/etc/systemd/system/`, and reloads systemd. Preview the commands with `python3 install.py remove ROLE --dry-run`. Removal leaves the role's `config.toml`, uv environment, and clone in place so it can be installed again later.

If the server reports `"gpu_temp":"N/A"`, check `nvidia-smi` and the GPU index. If `"cpu_temp":"N/A"`, adjust the CPU sensor settings. If the Pi shows a fetch error, check the URL, network reachability, and server service. On the Pi, the service account must have GPIO access.

## Development

The roles are separate uv projects with committed lockfiles. Run them manually after making a local config:

```bash
uv sync --project server --locked
uv run --project server python server/stats.py

uv sync --project client --locked
uv run --project client python client/lcd.py
```

To update dependencies, edit the role's `pyproject.toml`, run `uv lock --project ROLE`, and commit its `uv.lock`. The NVIDIA binding is installed as `nvidia-ml-py` and imported in Python as `pynvml`.

## Publishing to GitHub

The repository is initialized locally on the `main` branch with `origin` set to `https://github.com/albertodicaprio/lcd-panel-stats.git`. Create that GitHub repository if it does not already exist, then push after reviewing the files:

```bash
git push -u origin main
```
