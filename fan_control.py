#!/usr/bin/env python3
"""
Simple Raspberry Pi fan controller for CM5 module.

Features:
- Read CPU temperature via `/usr/bin/vcgencmd measure_temp` (with fallback to
  `/sys/class/thermal/thermal_zone0/temp`).
- Map temperature to PWM duty cycle with configurable thresholds.
- Minimal duty cycle = 25%. 100% at or above max_temp (default 60C).
- Safe GPIO abstraction: uses RPi.GPIO if available, otherwise DummyGPIO.
- Flags for dry-run and simulation for safe testing on non-RPi systems.

Usage examples:
  sudo python3 fan_control.py           # run using real GPIO and vcgencmd
  python3 fan_control.py --dry-run     # don't touch GPIO, just log decisions
  python3 fan_control.py --simulate-temp 50

"""
import argparse
import logging
import os
import re
import signal
import subprocess
import sys
import time
from typing import Optional

DEFAULT_PIN = 13
DEFAULT_FREQ = 50
DEFAULT_POLL_SECONDS = 5
DEFAULT_MIN_DUTY = 25.0
DEFAULT_MIN_TEMP = 45.0
DEFAULT_MAX_TEMP = 60.0

logger = logging.getLogger("sipeed-cm5-fancontrol")


class DummyPWM:
    def __init__(self, pin, freq):
        self.pin = pin
        self.freq = freq
        self._duty = None

    def start(self, duty):
        self._duty = duty
        logger.info("[DummyPWM] start duty=%.1f on pin %s freq %s", duty, self.pin, self.freq)

    def ChangeDutyCycle(self, duty):
        self._duty = duty
        logger.info("[DummyPWM] ChangeDutyCycle -> %.1f", duty)

    def stop(self):
        logger.info("[DummyPWM] stop")


class DummyGPIO:
    BCM = 'BCM'
    OUT = 'OUT'

    def setmode(self, m):
        logger.info("[DummyGPIO] setmode %s", m)

    def setup(self, pin, mode):
        logger.info("[DummyGPIO] setup pin=%s mode=%s", pin, mode)

    def PWM(self, pin, freq):
        return DummyPWM(pin, freq)

    def cleanup(self):
        logger.info("[DummyGPIO] cleanup")


def import_gpio(dry_run: bool):
    if dry_run:
        return DummyGPIO()
    try:
        import RPi.GPIO as GPIO  # type: ignore
        return GPIO
    except Exception:
        logger.warning("RPi.GPIO not available, falling back to DummyGPIO (dry-run mode)")
        return DummyGPIO()


def read_temp_vcgencmd() -> Optional[float]:
    path = "/usr/bin/vcgencmd"
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.check_output([path, "measure_temp"], stderr=subprocess.DEVNULL)
        s = out.decode("utf-8")
        m = re.search(r"temp=([0-9]+\.?[0-9]*)'C", s)
        if m:
            return float(m.group(1))
    except Exception as e:
        logger.debug("vcgencmd failed: %s", e)
    return None


def read_temp_sysfs() -> Optional[float]:
    # Linux thermal zone (millidegrees)
    path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(path, "r") as f:
            v = f.read().strip()
            if v:
                return float(v) / 1000.0
    except Exception as e:
        logger.debug("sysfs temp read failed: %s", e)
    return None


def read_cpu_temp(simulate_temp: Optional[float] = None) -> Optional[float]:
    if simulate_temp is not None:
        return float(simulate_temp)
    t = read_temp_vcgencmd()
    if t is not None:
        return t
    return read_temp_sysfs()


def temp_to_duty(temp_c: float, min_temp: float = DEFAULT_MIN_TEMP, max_temp: float = DEFAULT_MAX_TEMP, min_duty: float = DEFAULT_MIN_DUTY, max_duty: float = 100.0) -> float:
    """Map temperature to PWM duty cycle.

    - temp <= min_temp -> min_duty
    - temp >= max_temp -> max_duty
    - linear in-between
    """
    if temp_c <= min_temp:
        return float(min_duty)
    if temp_c >= max_temp:
        return float(max_duty)
    # linear interpolation
    ratio = (temp_c - min_temp) / (max_temp - min_temp)
    duty = min_duty + ratio * (max_duty - min_duty)
    return float(duty)


class FanController:
    def __init__(self, pin: int = DEFAULT_PIN, freq: int = DEFAULT_FREQ, poll: int = DEFAULT_POLL_SECONDS, dry_run: bool = False, min_temp: float = DEFAULT_MIN_TEMP, max_temp: float = DEFAULT_MAX_TEMP, min_duty: float = DEFAULT_MIN_DUTY, simulate_temp: Optional[float] = None):
        self.pin = pin
        self.freq = freq
        self.poll = poll
        self.dry_run = dry_run
        self.simulate_temp = simulate_temp
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.min_duty = min_duty
        self.last_duty = None
        self._running = False

        self.GPIO = import_gpio(dry_run=self.dry_run)
        # if real RPi.GPIO was imported, use its API, else DummyGPIO
        try:
            # If module is class-like (DummyGPIO), follow its API
            self.GPIO.setmode(self.GPIO.BCM)
        except Exception:
            # Some real GPIO modules expect module-level calls
            pass

        # create PWM instance
        try:
            self.GPIO.setup(self.pin, self.GPIO.OUT)
            self.pwm = self.GPIO.PWM(self.pin, self.freq)
        except Exception:
            # If module values are functions, call accordingly
            self.pwm = DummyPWM(self.pin, self.freq)

    def start(self):
        start_duty = self.min_duty
        self.pwm.start(start_duty)
        self.last_duty = start_duty
        self._running = True
        logger.info("Fan controller started: pin=%s freq=%s poll=%ss", self.pin, self.freq, self.poll)

    def stop(self):
        try:
            self.pwm.stop()
        except Exception:
            pass
        try:
            self.GPIO.cleanup()
        except Exception:
            pass
        self._running = False
        logger.info("Fan controller stopped")

    def run_once(self) -> Optional[dict]:
        t = read_cpu_temp(self.simulate_temp)
        if t is None:
            logger.error("Failed to read CPU temperature")
            return None
        duty = temp_to_duty(t, self.min_temp, self.max_temp, self.min_duty)
        # clamp
        duty = max(self.min_duty, min(100.0, duty))
        # apply small hysteresis: only change if >1% difference
        if self.last_duty is None or abs(duty - self.last_duty) >= 1.0:
            try:
                # real PWM ChangeDutyCycle or Dummy implementation
                self.pwm.ChangeDutyCycle(duty)
                logger.info("Temp %.2f°C -> duty %.1f%%", t, duty)
            except Exception as e:
                logger.warning("Failed to set duty cycle: %s", e)
        self.last_duty = duty
        return {"temp": t, "duty": duty}

    def run_loop(self):
        self.start()
        def _sigterm(signum, frame):
            logger.info("Received signal %s, stopping", signum)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGINT, _sigterm)

        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.exception("Error in run loop: %s", e)
            time.sleep(self.poll)


def parse_args():
    p = argparse.ArgumentParser(description="Sipeed CM5 fan controller for Raspberry Pi")
    p.add_argument("--pin", type=int, default=DEFAULT_PIN, help="GPIO pin (BCM) to use")
    p.add_argument("--freq", type=int, default=DEFAULT_FREQ, help="PWM frequency")
    p.add_argument("--poll", type=int, default=DEFAULT_POLL_SECONDS, help="Poll interval seconds")
    p.add_argument("--min-temp", type=float, default=DEFAULT_MIN_TEMP, help="Temperature (C) at which min duty is used")
    p.add_argument("--max-temp", type=float, default=DEFAULT_MAX_TEMP, help="Temperature (C) at which 100%% duty is used")
    p.add_argument("--min-duty", type=float, default=DEFAULT_MIN_DUTY, help="Minimum duty percent")
    p.add_argument("--dry-run", action="store_true", help="Don't touch GPIO; use DummyGPIO and log only")
    p.add_argument("--simulate-temp", type=float, default=None, help="Simulate a fixed temperature (C) for testing")
    p.add_argument("--verbose", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    controller = FanController(pin=args.pin, freq=args.freq, poll=args.poll, dry_run=args.dry_run, min_temp=args.min_temp, max_temp=args.max_temp, min_duty=args.min_duty, simulate_temp=args.simulate_temp)
    controller.run_loop()


if __name__ == "__main__":
    main()
