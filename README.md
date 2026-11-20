# LCD panel stats

The **server** exposes CPU temperature and usage, NVIDIA GPU temperature, RAM use, and network speeds as JSON. The **client** displays stats on a Raspberry Pi character LCD. An optional **CPU gauge** uses the CPU usage value to move a servo needle on a Raspberry Pi.

## Requirements

- Server: Linux, Python 3.11 or newer, an NVIDIA GPU with a working driver (`nvidia-smi` should work), and network access from the Pi.
- Client: Raspberry Pi running Linux with Python 3.11 or newer, a supported GPIO setup, and a character LCD wired to the pins in `client/config.example.toml` (or edit the pins in `client/config.toml`). On Raspberry Pi OS, install build prerequisites with `sudo apt install python3-dev build-essential swig liblgpio-dev` before running the installer. The GPIO dependencies build native code; `RPi.GPIO` needs `Python.h`, and `lgpio` needs SWIG and the system `liblgpio` library.
- CPU gauge: Raspberry Pi running Linux with Python 3.11 or newer and a servo connected to the configured BCM GPIO pin. Install the `lgpio` build prerequisites with `sudo apt install python3-dev build-essential swig liblgpio-dev` before running its installer.
- All hosts: [uv](https://docs.astral.sh/uv/getting-started/installation/), `git`, and `sudo` access to install a systemd service.

Clone the repository on the server and each Raspberry Pi that will run a client. Run the installer as the normal account that will run the service:

```bash
git clone https://github.com/albertodicaprio/lcd-panel-stats.git
cd lcd-panel-stats
python3 install.py server  # on the NVIDIA machine
python3 install.py client  # on the Raspberry Pi
python3 install.py cpu_gauge  # optional, on the gauge Raspberry Pi
```

The server installer asks for the HTTP port, GPU index, and CPU temperature sensor and labels; defaults match the original setup. The client and CPU gauge installers ask for the server hostname or IP address and port. Each installer creates its role's ignored `config.toml`, runs `uv sync --locked`, writes a systemd unit under `/etc/systemd/system/`, and enables and starts it. It derives the service user's name and paths from the current account and clone location. Run `python3 install.py --dry-run ROLE` to inspect the config and unit before installation.

Start the server before the client. Ensure the server's chosen port is reachable from the Pi. Test it with `curl http://SERVER_HOST:5000/stats`. The server listens on all interfaces by default; set `bind_host` in `server/config.toml` if a different interface is needed. The HTTP endpoint has no authentication, so use it only on a trusted network or behind suitable network controls.

The `/stats` JSON includes `cpu_usage_percent`, a number from 0 to 100 representing overall CPU use sampled over 0.1 seconds. The CPU gauge uses this field; the LCD client does not display it.

## Configuration

The installer keeps existing `config.toml` files when run again. Edit them to change settings, then restart the relevant service. The tracked example files describe every setting:

- `server/config.example.toml`: HTTP bind host and port, NVIDIA GPU index, CPU sensor name and preferred sensor labels. The default CPU sensor is `k10temp` with `Tccd1` then `Tctl`, matching the original AMD setup. For other CPUs, inspect the available names with `sensors` or `uv run --project server python -c 'import psutil; print(psutil.sensors_temperatures())'`.
- `client/config.example.toml`: server URL, request timeout, LCD dimensions and BCM pin numbers, refresh interval, and optional shutdown button. The default LCD wiring is RS=26, E=19, data=25,24,22,27.
- `cpu_gauge/config.example.toml`: server URL, request timeout, servo BCM pin (default 17), poll interval, needle update interval, and maximum movement per update. The installer copies this to `cpu_gauge/config.toml` and fills in the server address.

### CPU gauge wiring

Connect the servo signal wire to **GPIO 17 (BCM)**, or change `pin` in `cpu_gauge/config.toml`. Power the servo from a supply rated for its current and connect the supply ground to the Pi ground. If the LCD client and gauge run on the same Pi, use distinct GPIO pins for the servo, LCD, and optional shutdown button. The gauge maps 0% CPU usage to one end of travel and 100% to the other; `max_step` limits movement per update. Verify the direction and physical travel on the Pi before attaching the needle.

To test servo travel without the server, stop the gauge service if it is running, then start manual mode from the repository root on the Pi:

```bash
sudo systemctl stop lcd-stats-cpu-gauge.service
uv run --project cpu_gauge python cpu_gauge/cpu_gauge.py --manual
```

Enter `0`, `50`, and `100` to move from one end through the middle to the other. Enter `q` to quit. Manual mode uses the configured pin, `max_step`, and `update_seconds`; test with the needle detached first. Restart the service afterward with `sudo systemctl start lcd-stats-cpu-gauge.service`.

### Raspberry Pi shutdown button

Wire a normally open push button between **GPIO 17 (BCM)** and **GND**. The client enables GPIO's internal pull-up, so no external resistor is needed. Keep the button on a pin that is not used by the LCD. In `client/config.toml`, add or update:

```toml
[shutdown_button]
enabled = true
pin = 17
bounce_time_seconds = 0.1
```

Run `python3 install.py client` again on the Pi after enabling the button. The installer adds `/etc/sudoers.d/lcd-stats-client`, granting only the client service account passwordless access to `/usr/bin/systemctl poweroff`. The client invokes it with `sudo -n` when the button is pressed; do not run the whole client service as root. The installer removes this permission if the button is later disabled or the client service is removed. Inspect the planned permission with `python3 install.py --dry-run client`.

Pressing the button starts an immediate system shutdown. Save any work on the Pi before testing it. Hardware operation must be checked on the Pi; local tests can check configuration and command wiring only.

Configuration is read from the role's `config.toml` by default. For a temporary override, set `LCD_STATS_CONFIG` to an absolute TOML file path. Keep the client URL pointed at `/stats`.

## Service checks

```bash
systemctl status lcd-stats-server.service
systemctl status lcd-stats-client.service
systemctl status lcd-stats-cpu-gauge.service
journalctl -u lcd-stats-server.service -f
journalctl -u lcd-stats-client.service -f
journalctl -u lcd-stats-cpu-gauge.service -f
```

Run these commands on the machine hosting the relevant role. After editing config, restart the matching service with `sudo systemctl restart SERVICE_NAME`. Re-run `python3 install.py ROLE` after moving the clone or upgrading dependencies so uv and systemd use the new location.

To uninstall a service on its machine, run `python3 install.py remove ROLE`, where `ROLE` is `server`, `client`, or `cpu_gauge`. This stops and disables the service, removes its unit from `/etc/systemd/system/`, and reloads systemd. LCD client removal also removes the shutdown button's sudoers permission if present. Preview the commands with `python3 install.py remove ROLE --dry-run`. Removal leaves the role's `config.toml`, uv environment, and clone in place so it can be installed again later.

If the server reports `"gpu_temp":"N/A"`, check `nvidia-smi` and the GPU index. If `"cpu_temp":"N/A"`, adjust the CPU sensor settings. If the Pi shows a fetch error, check the URL, network reachability, and server service. On the Pi, the service account must have GPIO access.

If the client dependency installation fails with `Python.h: No such file or directory`, install `python3-dev` as above and rerun `python3 install.py client`. If the error persists, check which Python uv selected with `uv python find --project client`; its version must match the installed development headers.

If the `lgpio` build fails with `cannot find -llgpio`, install `liblgpio-dev` and rerun `python3 install.py client`.

If the CPU gauge reports a fetch error, check `cpu_gauge/config.toml` and `curl http://SERVER_HOST:5000/stats` from the Pi. If the servo does not move, check its power, shared ground, signal pin, and GPIO access for the service user.

## Development

The roles are separate uv projects with committed lockfiles. Run them manually after making a local config:

```bash
uv sync --project server --locked
uv run --project server python server/stats.py

uv sync --project client --locked
uv run --project client python client/lcd.py

uv sync --project cpu_gauge --locked
uv run --project cpu_gauge python cpu_gauge/cpu_gauge.py
```

To update dependencies, edit the role's `pyproject.toml`, run `uv lock --project ROLE`, and commit its `uv.lock`. The NVIDIA binding is installed as `nvidia-ml-py` and imported in Python as `pynvml`.

## Publishing to GitHub

The repository is initialized locally on the `main` branch with `origin` set to `https://github.com/albertodicaprio/lcd-panel-stats.git`. Create that GitHub repository if it does not already exist, then push after reviewing the files:

```bash
git push -u origin main
```
