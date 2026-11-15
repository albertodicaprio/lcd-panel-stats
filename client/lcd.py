"""Display the server's statistics on a Raspberry Pi character LCD."""

import os
import subprocess
import time
import tomllib
from pathlib import Path

import requests


def load_config():
    path = Path(os.environ.get("LCD_STATS_CONFIG", Path(__file__).with_name("config.toml")))
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def page_cpu_gpu(data):
    return f"CPU:{data['cpu_temp']:>3}C", f"GPU:{data['gpu_temp']:>3}C"


def page_ram(data):
    ram_percent = round(data["ram_used_gb"] / data["ram_total_gb"] * 100)
    return f"RAM%:{ram_percent:>3}", f"RAM:{data['ram_used_gb']:>4}/{data['ram_total_gb']}"


def page_network(data):
    return f"UP:{data['net_sent_kbs']:>5}KB/s", f"DN:{data['net_recv_kbs']:>5}KB/s"


def request_shutdown():
    subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "poweroff"], check=True)


def main():
    from RPLCD.gpio import CharLCD, GPIO
    from gpiozero import Button, Device
    from gpiozero.pins.lgpio import LGPIOFactory

    config = load_config()
    display = config["display"]
    server = config["server"]
    Device.pin_factory = LGPIOFactory()
    lcd = CharLCD(
        numbering_mode=GPIO.BCM,
        cols=display["columns"],
        rows=display["rows"],
        pin_rs=display["pin_rs"],
        pin_e=display["pin_e"],
        pins_data=display["pins_data"],
    )
    pages = (page_cpu_gpu, page_ram, page_network)
    page_index = 0
    button = None
    try:
        shutdown = config.get("shutdown_button", {})
        if shutdown.get("enabled", False):
            pin = shutdown["pin"]
            if pin in (display["pin_rs"], display["pin_e"], *display["pins_data"]):
                raise ValueError(f"Shutdown button GPIO {pin} is already used by the LCD")
            button = Button(pin, pull_up=True, bounce_time=shutdown["bounce_time_seconds"])
            button.when_pressed = request_shutdown

        while True:
            try:
                response = requests.get(server["url"], timeout=server["timeout_seconds"])
                response.raise_for_status()
                line1, line2 = pages[page_index](response.json())
                page_index = (page_index + 1) % len(pages)
            except (requests.RequestException, KeyError, ValueError, TypeError, ZeroDivisionError) as error:
                line1, line2 = "Error fetching", str(error)

            lcd.clear()
            lcd.cursor_pos = (0, 0)
            lcd.write_string(line1[:display["columns"]])
            lcd.cursor_pos = (1, 0)
            lcd.write_string(line2[:display["columns"]])
            time.sleep(display["refresh_seconds"])
    except KeyboardInterrupt:
        pass
    finally:
        if button is not None:
            button.close()
        lcd.clear()


if __name__ == "__main__":
    main()
