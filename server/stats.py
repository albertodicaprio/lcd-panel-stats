"""HTTP endpoint for the host's CPU, GPU, RAM, and network statistics."""

import os
import time
import tomllib
from pathlib import Path

import psutil
import pynvml
from flask import Flask, jsonify


def load_config():
    path = Path(os.environ.get("LCD_STATS_CONFIG", Path(__file__).with_name("config.toml")))
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


config = load_config()
app = Flask(__name__)
net_prev = psutil.net_io_counters()
time_prev = time.monotonic()
gpu_handle = None


def get_nvidia_gpu_temp():
    global gpu_handle
    try:
        if gpu_handle is None:
            pynvml.nvmlInit()
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(config["gpu"]["index"])
        return pynvml.nvmlDeviceGetTemperature(gpu_handle, pynvml.NVML_TEMPERATURE_GPU)
    except pynvml.NVMLError:
        gpu_handle = None
        return "N/A"


def get_cpu_temp():
    cpu = config["cpu"]
    entries = psutil.sensors_temperatures().get(cpu["sensor"], [])
    for label in cpu["preferred_labels"]:
        for entry in entries:
            if entry.label == label:
                return round(entry.current, 1)
    return "N/A"


def get_network_speed():
    global net_prev, time_prev
    net_now = psutil.net_io_counters()
    now = time.monotonic()
    interval = now - time_prev
    sent = max(0, net_now.bytes_sent - net_prev.bytes_sent)
    received = max(0, net_now.bytes_recv - net_prev.bytes_recv)
    net_prev, time_prev = net_now, now
    if interval <= 0:
        return 0.0, 0.0
    return round(sent / 1024 / interval, 1), round(received / 1024 / interval, 1)


@app.route("/stats")
def stats():
    ram = psutil.virtual_memory()
    net_sent, net_recv = get_network_speed()
    return jsonify({
        "cpu_temp": get_cpu_temp(),
        "cpu_usage_percent": round(psutil.cpu_percent(interval=0.1), 1),
        "gpu_temp": get_nvidia_gpu_temp(),
        "ram_used_gb": round((ram.total - ram.available) / (1024 ** 3), 2),
        "ram_total_gb": round(ram.total / (1024 ** 3), 2),
        "net_sent_kbs": net_sent,
        "net_recv_kbs": net_recv,
    })


if __name__ == "__main__":
    app.run(host=config["server"]["bind_host"], port=config["server"]["port"])
