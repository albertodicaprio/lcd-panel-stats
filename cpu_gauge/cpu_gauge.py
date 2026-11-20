"""Drive a Raspberry Pi servo gauge from the server's CPU usage metric."""

import argparse
import json
import math
import os
import time
import tomllib
import urllib.request
from pathlib import Path


def load_config():
    path = Path(os.environ.get("LCD_STATS_CONFIG", Path(__file__).with_name("config.toml")))
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def get_cpu_usage(url, timeout):
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Pi-CPU-Gauge"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            cpu = float(json.load(response)["cpu_usage_percent"])
        if not math.isfinite(cpu):
            raise ValueError("CPU usage must be a finite number")
        return cpu
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Failed to fetch CPU usage: {error}")
        return None


def cpu_to_servo(cpu):
    return max(-1.0, min(1.0, cpu / 50.0 - 1.0))


def move_toward(current, target, max_step):
    return current + max(-max_step, min(max_step, target - current))


def manual_test(servo, gauge):
    position = -1.0
    print("Enter CPU usage from 0 to 100; enter q to quit.")
    while True:
        try:
            answer = input("CPU usage %: ").strip()
        except EOFError:
            return
        if answer.lower() == "q":
            return
        try:
            percent = float(answer)
            if not math.isfinite(percent) or not 0 <= percent <= 100:
                raise ValueError
        except ValueError:
            print("Enter a number from 0 to 100, or q to quit.")
            continue

        target = cpu_to_servo(percent)
        while position != target:
            position = move_toward(position, target, gauge["max_step"])
            servo.value = position
            time.sleep(gauge["update_seconds"])
        print(f"Gauge set to {percent:g}%")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manual", action="store_true", help="move the servo using values entered at the prompt")
    args = parser.parse_args()

    config = load_config()
    server = config["server"]
    gauge = config["gauge"]
    if server["timeout_seconds"] <= 0 or gauge["poll_seconds"] <= 0 or gauge["update_seconds"] <= 0:
        raise ValueError("Timeout and update intervals must be positive")
    if not 0 < gauge["max_step"] <= 2:
        raise ValueError("Gauge max_step must be between 0 and 2")

    from gpiozero import Device, Servo
    from gpiozero.pins.lgpio import LGPIOFactory

    Device.pin_factory = LGPIOFactory()
    servo = Servo(gauge["pin"], initial_value=-1)
    current_position = target_position = -1.0
    last_poll = float("-inf")
    try:
        servo.value = current_position
        if args.manual:
            manual_test(servo, gauge)
            return
        print(f"CPU gauge started. Fetching stats from {server['url']}")
        while True:
            now = time.monotonic()
            if now - last_poll >= gauge["poll_seconds"]:
                cpu = get_cpu_usage(server["url"], server["timeout_seconds"])
                if cpu is not None:
                    target_position = cpu_to_servo(cpu)
                    print(f"CPU: {cpu:5.1f}%")
                last_poll = time.monotonic()

            current_position = move_toward(current_position, target_position, gauge["max_step"])
            servo.value = current_position
            time.sleep(gauge["update_seconds"])
    except KeyboardInterrupt:
        print("\nStopping CPU gauge...")
    finally:
        servo.close()


if __name__ == "__main__":
    main()
