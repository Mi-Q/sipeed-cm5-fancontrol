#!/usr/bin/env python3
"""
Simple Raspberry Pi fan controller for CM5 module.

Copyright (c) 2025 Michael Kuppinger (Mi-Q)
Contact: michael@kuppinger.eu
Licensed under the MIT License - see LICENSE file for details.

Version: 0.2.0

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

DEFAULT_PIN = 13
DEFAULT_FREQ = 50
DEFAULT_POLL_SECONDS = 5
DEFAULT_MIN_DUTY = 25.0
DEFAULT_MIN_TEMP = 45.0
DEFAULT_MAX_TEMP = 60.0

logger = logging.getLogger("sipeed-cm5-fancontrol")


class DummyPWM:
    """Mock PWM implementation for testing and dry-run mode."""

    def __init__(self, pin, freq):
        """Initialize dummy PWM controller.

        Args:
            pin (int): GPIO pin number
            freq (int): PWM frequency in Hz
        """
        self.pin = pin
        self.freq = freq
        self._duty = None

    def start(self, duty):
        """Start PWM with given duty cycle.

        Args:
            duty (float): Initial duty cycle percentage
        """
        self._duty = duty
        logger.info(
            "[DummyPWM] start duty=%.1f on pin %s freq %s", duty, self.pin, self.freq
        )

    def change_duty_cycle(self, duty):
        """Change PWM duty cycle.

        Args:
            duty (float): New duty cycle percentage
        """
        self._duty = duty
        logger.info("[DummyPWM] change_duty_cycle -> %.1f", duty)

    # Alias for RPi.GPIO compatibility
    ChangeDutyCycle = change_duty_cycle

    def stop(self):
        """Stop PWM output."""
        logger.info("[DummyPWM] stop")


class DummyGPIO:
    """Mock GPIO implementation for testing and dry-run mode.

    Provides a subset of RPi.GPIO functionality for testing on non-RPi systems.
    """

    BCM = "BCM"
    OUT = "OUT"

    def setmode(self, m):
        """Set GPIO mode (BCM/BOARD).

        Args:
            m (str): GPIO mode identifier
        """
        logger.info("[DummyGPIO] setmode %s", m)

    def setup(self, pin, mode):
        """Configure GPIO pin mode.

        Args:
            pin (int): GPIO pin number
            mode (str): Pin mode (IN/OUT)
        """
        logger.info("[DummyGPIO] setup pin=%s mode=%s", pin, mode)

    def pwm(self, pin, freq):
        """Create PWM instance for given pin.

        Args:
            pin (int): GPIO pin number
            freq (int): PWM frequency in Hz

        Returns:
            DummyPWM: PWM controller instance
        """
        return DummyPWM(pin, freq)

    # Alias for RPi.GPIO compatibility
    PWM = pwm

    def cleanup(self):
        """Clean up GPIO resources."""
        logger.info("[DummyGPIO] cleanup")


def import_gpio(dry_run: bool):
    """Import GPIO module or return dummy implementation.

    Args:
        dry_run (bool): If True, always return dummy implementation

    Returns:
        module: RPi.GPIO module or DummyGPIO instance

    Note:
        When not in dry-run mode, attempts to import RPi.GPIO first
    """
    if dry_run:
        return DummyGPIO()
    try:
        # Import the GPIO module using the module-level name to match common usage
        # and avoid namespace issues (returns module object as GPIO)
        import RPi.GPIO as GPIO

        return GPIO
    except ImportError:
        logger.warning(
            "RPi.GPIO not available, falling back to DummyGPIO (dry-run mode)"
        )
        return DummyGPIO()


def read_temp_vcgencmd() -> Optional[float]:
    """Read CPU temperature using vcgencmd tool.

    Returns:
        Optional[float]: Temperature in Celsius or None if reading fails
    """
    path = "/usr/bin/vcgencmd"
    if not os.path.exists(path):
        return None
    try:
        out = subprocess.check_output([path, "measure_temp"], stderr=subprocess.DEVNULL)
        s = out.decode("utf-8")
        m = re.search(r"temp=([0-9]+\.?[0-9]*)'C", s)
        if m:
            return float(m.group(1))
    except (subprocess.SubprocessError, ValueError) as e:
        logger.debug("vcgencmd failed: %s", e)
    return None


def read_temp_sysfs() -> Optional[float]:
    """Read CPU temperature from sysfs thermal zone.

    Returns:
        Optional[float]: Temperature in Celsius or None if reading fails
    """
    # Linux thermal zone (millidegrees)
    path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return float(v) / 1000.0
    except (IOError, ValueError) as e:
        logger.debug("sysfs temp read failed: %s", e)
    return None


def read_cpu_temp(simulate_temp: Optional[float] = None) -> Optional[float]:
    """Read CPU temperature with optional simulation.

    Args:
        simulate_temp: Optional simulated temperature for testing

    Returns:
        Optional[float]: Temperature in Celsius or None if all methods fail
    """
    if simulate_temp is not None:
        return float(simulate_temp)
    t = read_temp_vcgencmd()
    if t is not None:
        return t
    return read_temp_sysfs()


def read_remote_temp_ssh(target: str, timeout: int = 5) -> Optional[float]:
    """Read temperature on remote host via ssh. `target` may be 'user@host' or 'host'.

    Requires passwordless SSH (recommended) or an SSH agent.
    Falls back to reading /sys/class/thermal/thermal_zone0/temp if vcgencmd missing.
    """
    # We'll try vcgencmd first, then sysfs
    cmd_vcgencmd = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={timeout}",
        target,
        "/usr/bin/vcgencmd measure_temp",
    ]
    try:
        out = subprocess.check_output(
            cmd_vcgencmd, stderr=subprocess.DEVNULL, timeout=timeout + 2
        )
        s = out.decode("utf-8")
        m = re.search(r"temp=([0-9]+\.?[0-9]*)'C", s)
        if m:
            return float(m.group(1))
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        # try sysfs
        cmd_sysfs = [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            f"ConnectTimeout={timeout}",
            target,
            "cat /sys/class/thermal/thermal_zone0/temp",
        ]
        try:
            out = subprocess.check_output(
                cmd_sysfs, stderr=subprocess.DEVNULL, timeout=timeout + 2
            )
            s = out.decode("utf-8").strip()
            if s:
                return float(s) / 1000.0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None
    return None


def read_remote_temp_http(url: str, timeout: int = 5) -> Optional[float]:
    """Read temperature via HTTP endpoint that returns a plain number (C).

    Minimal implementation using curl to avoid new Python dependencies.
    URL must be reachable.

    Args:
        url: HTTP endpoint URL
        timeout: Request timeout in seconds

    Returns:
        Optional[float]: Temperature in Celsius or None if request fails
    """
    try:
        out = subprocess.check_output(
            ["curl", "-s", "--max-time", str(timeout), url],
            stderr=subprocess.DEVNULL,
            timeout=timeout + 1,
        )
        s = out.decode("utf-8").strip()
        if not s:
            return None
        return float(s)
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError):
        return None


def temp_to_duty(
    temp_c: float,
    min_temp: float = DEFAULT_MIN_TEMP,
    max_temp: float = DEFAULT_MAX_TEMP,
    min_duty: float = DEFAULT_MIN_DUTY,
    max_duty: float = 100.0,
) -> float:
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
    """PWM fan controller for Raspberry Pi.

    Controls fan speed based on CPU temperature using PWM output.
    Supports local and remote temperature monitoring with aggregation.
    """

    def __init__(
        self,
        pin: int = DEFAULT_PIN,
        freq: int = DEFAULT_FREQ,
        poll: int = DEFAULT_POLL_SECONDS,
        dry_run: bool = False,
        min_temp: float = DEFAULT_MIN_TEMP,
        max_temp: float = DEFAULT_MAX_TEMP,
        min_duty: float = DEFAULT_MIN_DUTY,
        simulate_temp: Optional[float] = None,
    ):
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
        # remote peers
        self.peers: List[str] = []
        self.remote_method = "ssh"  # or 'http'
        self.remote_timeout = 5
        self.aggregate = "max"  # or 'avg'

        self.GPIO = import_gpio(dry_run=self.dry_run)
        # if real RPi.GPIO was imported, use its API, else DummyGPIO
        try:
            # If module is class-like (DummyGPIO), follow its API
            self.GPIO.setmode(self.GPIO.BCM)
        except AttributeError:
            # Some real GPIO modules expect module-level calls
            pass

        # create PWM instance
        try:
            self.GPIO.setup(self.pin, self.GPIO.OUT)
            self.pwm = self.GPIO.PWM(self.pin, self.freq)
        except AttributeError:
            # If module values are functions, call accordingly
            self.pwm = DummyPWM(self.pin, self.freq)

    def start(self):
        """Start the fan controller with initial duty cycle."""
        start_duty = self.min_duty
        self.pwm.start(start_duty)
        self.last_duty = start_duty
        self._running = True
        logger.info(
            "Fan controller started: pin=%s freq=%s poll=%ss",
            self.pin,
            self.freq,
            self.poll,
        )

    def stop(self):
        """Stop the fan controller and clean up GPIO resources."""
        try:
            self.pwm.stop()
        except AttributeError:
            pass
        try:
            self.GPIO.cleanup()
        except AttributeError:
            pass
        self._running = False
        logger.info("Fan controller stopped")

    def run_once(self) -> Optional[dict]:
        """Execute one iteration of temperature check and fan control.

        Returns:
            Optional[dict]: Dictionary with temperatures and duty cycle,
                or None on failure
        """
        local_t = read_cpu_temp(self.simulate_temp)
        if local_t is None:
            logger.error("Failed to read local CPU temperature")
            return None

        temps = {"local": local_t}

        # poll peers in parallel
        if self.peers:
            with ThreadPoolExecutor(max_workers=min(8, len(self.peers))) as ex:
                futures = {
                    ex.submit(
                        (
                            read_remote_temp_ssh
                            if self.remote_method == "ssh"
                            else read_remote_temp_http
                        ),
                        p,
                        self.remote_timeout,
                    ): p
                    for p in self.peers
                }

                for fut in as_completed(futures):
                    peer = futures[fut]
                    try:
                        tv = fut.result()
                        temps[peer] = tv
                    except (OSError, ValueError, subprocess.SubprocessError) as e:
                        logger.debug("Error polling %s: %s", peer, e)

        # compute aggregate temperature used to decide fan speed
        valid_temps = [v for v in temps.values() if v is not None]
        if not valid_temps:
            logger.error("No valid temperature readings (local or peers)")
            return None

        if self.aggregate == "max":
            t = max(valid_temps)
        else:
            t = sum(valid_temps) / len(valid_temps)

        duty = temp_to_duty(t, self.min_temp, self.max_temp, self.min_duty)
        # clamp
        duty = max(self.min_duty, min(100.0, duty))
        # apply small hysteresis: only change if >1% difference
        if self.last_duty is None or abs(duty - self.last_duty) >= 1.0:
            try:
                # real PWM ChangeDutyCycle or Dummy implementation
                self.pwm.ChangeDutyCycle(duty)
                logger.info("Temp %.2f°C -> duty %.1f%%", t, duty)
            except AttributeError as e:
                logger.warning("Failed to set duty cycle: %s", e)
        self.last_duty = duty
        result = {"aggregated_temp": t, "duty": duty, "per_host": temps}
        return result

    def run_loop(self):
        """Main control loop: monitor temperature and adjust fan speed continuously."""
        self.start()

        def _sigterm(signum, _frame):
            logger.info("Received signal %s, stopping", signum)
            self.stop()
            sys.exit(0)

        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGINT, _sigterm)

        while True:
            try:
                self.run_once()
            except KeyboardInterrupt:
                raise
            except (OSError, ValueError) as e:
                logger.exception("Error in run loop: %s", e)
            time.sleep(self.poll)


def parse_args():
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed arguments
    """
    p = argparse.ArgumentParser(
        description="Sipeed CM5 fan controller for Raspberry Pi"
    )
    p.add_argument("--pin", type=int, default=DEFAULT_PIN, help="GPIO pin (BCM) to use")
    p.add_argument("--freq", type=int, default=DEFAULT_FREQ, help="PWM frequency")
    p.add_argument(
        "--poll", type=int, default=DEFAULT_POLL_SECONDS, help="Poll interval seconds"
    )
    p.add_argument(
        "--min-temp",
        type=float,
        default=DEFAULT_MIN_TEMP,
        help="Temperature (C) at which min duty is used",
    )
    p.add_argument(
        "--max-temp",
        type=float,
        default=DEFAULT_MAX_TEMP,
        help="Temperature (C) at which 100%% duty is used",
    )
    p.add_argument(
        "--min-duty", type=float, default=DEFAULT_MIN_DUTY, help="Minimum duty percent"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't touch GPIO; use DummyGPIO and log only",
    )
    p.add_argument(
        "--simulate-temp",
        type=float,
        default=None,
        help="Simulate a fixed temperature (C) for testing",
    )
    p.add_argument("--verbose", action="store_true")
    p.add_argument(
        "--peers",
        type=str,
        default="",
        help="Comma-separated list of peers to poll (host or user@host)",
    )
    p.add_argument(
        "--remote-method",
        choices=("ssh", "http"),
        default="ssh",
        help="How to poll peers: ssh or http",
    )
    p.add_argument(
        "--aggregate",
        choices=("max", "avg"),
        default="max",
        help="Aggregate mode for peer temps",
    )
    p.add_argument(
        "--remote-timeout", type=int, default=5, help="Timeout seconds for remote polls"
    )
    return p.parse_args()


def main():
    """Main entry point for the fan controller application."""
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    controller = FanController(
        pin=args.pin,
        freq=args.freq,
        poll=args.poll,
        dry_run=args.dry_run,
        min_temp=args.min_temp,
        max_temp=args.max_temp,
        min_duty=args.min_duty,
        simulate_temp=args.simulate_temp,
    )
    # wire CLI options for remote polling
    if args.peers:
        controller.peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    controller.remote_method = args.remote_method
    controller.aggregate = args.aggregate
    controller.remote_timeout = args.remote_timeout
    controller.run_loop()


if __name__ == "__main__":
    main()
