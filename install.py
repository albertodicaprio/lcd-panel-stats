#!/usr/bin/env python3
"""Install or remove a client or server systemd service on this machine."""

import argparse
import getpass
import json
import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parent
SERVICES = {"client": "lcd-stats-client.service", "server": "lcd-stats-server.service"}


def ask(prompt, default=None):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        answer = input(f"{prompt}{suffix}: ").strip() or default
        if answer:
            return answer
        print("A value is required.")


def ask_port():
    while True:
        value = ask("Server port", "5000")
        if value.isdecimal() and 1 <= int(value) <= 65535:
            return int(value)
        print("Enter a port between 1 and 65535.")


def ask_host():
    while True:
        host = ask("Server hostname or IP address")
        if all(char.isalnum() or char in ".-:" for char in host):
            return host
        print("Enter a hostname or IP address without a scheme or path.")


def service_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def remove_service(role, dry_run):
    service_name = SERVICES[role]
    service_path = Path("/etc/systemd/system") / service_name
    if not service_path.exists():
        print(f"No unit found at {service_path}; nothing to remove.")
        return

    commands = [
        ["sudo", "systemctl", "disable", "--now", service_name],
        ["sudo", "rm", "--", str(service_path)],
        ["sudo", "systemctl", "daemon-reload"],
    ]
    if dry_run:
        for command in commands:
            print("Would run:", " ".join(command))
        return

    for command in commands:
        subprocess.run(command, check=True)
    print(f"Removed {service_name}. Configuration and uv dependencies remain in {ROOT / role}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_or_role", nargs="?", choices=("install", "remove", *SERVICES))
    parser.add_argument("role", nargs="?", choices=SERVICES)
    parser.add_argument("--dry-run", action="store_true", help="show planned actions without changing anything")
    args = parser.parse_args()

    command = args.command_or_role if args.command_or_role in ("install", "remove") else "install"
    if args.command_or_role in SERVICES:
        if args.role:
            parser.error("specify one role only")
        role = args.command_or_role
    else:
        role = args.role or ask(f"{command.capitalize()} client or server").lower()
    if role not in SERVICES:
        parser.error("role must be client or server")
    if os.geteuid() == 0:
        parser.error("run this script as the service user, without sudo")
    if command == "remove":
        remove_service(role, args.dry_run)
        return

    app_dir = ROOT / role
    config_path = app_dir / "config.toml"
    config_text = None
    if not config_path.exists():
        config_text = (app_dir / "config.example.toml").read_text()
        if role == "client":
            host = ask_host()
            port = ask_port()
            config_text = config_text.replace("YOUR_SERVER_HOST:5000", f"{host}:{port}")
        else:
            port = ask_port()
            gpu_index = ask("NVIDIA GPU index", "0")
            while not gpu_index.isdecimal():
                print("Enter a nonnegative GPU index.")
                gpu_index = ask("NVIDIA GPU index", "0")
            sensor = ask("CPU temperature sensor", "k10temp")
            labels = ask("Preferred CPU temperature labels (comma separated)", "Tccd1,Tctl")
            label_list = [label.strip() for label in labels.split(",") if label.strip()]
            config_text = config_text.replace("port = 5000", f"port = {port}", 1)
            config_text = config_text.replace("index = 0", f"index = {int(gpu_index)}", 1)
            config_text = config_text.replace('sensor = "k10temp"', f"sensor = {json.dumps(sensor)}", 1)
            config_text = config_text.replace('["Tccd1", "Tctl"]', json.dumps(label_list), 1)

    uv = shutil.which("uv")
    if uv is None:
        parser.error("uv is required; install it first using the README instructions")
    script = app_dir / ("lcd.py" if role == "client" else "stats.py")
    unit = "\n".join([
        "[Unit]",
        f"Description=LCD panel stats {role}",
        "Wants=network-online.target" if role == "client" else "After=network.target",
        "After=network-online.target" if role == "client" else "",
        "",
        "[Service]",
        f"User={getpass.getuser()}",
        f"WorkingDirectory={str(app_dir).replace('%', '%%')}",
        f"ExecStart={service_quote(uv)} run --project {service_quote(app_dir)} --no-sync python {service_quote(script)}",
        "Restart=always",
        "RestartSec=5",
        "",
        "[Install]",
        "WantedBy=multi-user.target",
        "",
    ])
    service_path = Path("/etc/systemd/system") / SERVICES[role]

    if args.dry_run:
        print(f"Config: {config_path}\n{config_text or '(existing file retained)'}")
        print(f"Service: {service_path}\n{unit}")
        return

    if config_text is not None:
        config_path.write_text(config_text)
    subprocess.run([uv, "sync", "--project", str(app_dir), "--locked"], check=True)
    subprocess.run(["sudo", "install", "-m", "0644", "/dev/stdin", str(service_path)], input=unit, text=True, check=True)
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)
    subprocess.run(["sudo", "systemctl", "enable", "--now", SERVICES[role]], check=True)
    subprocess.run(["sudo", "systemctl", "restart", SERVICES[role]], check=True)
    print(f"Installed {SERVICES[role]}. Check: systemctl status {SERVICES[role]}")


if __name__ == "__main__":
    main()
