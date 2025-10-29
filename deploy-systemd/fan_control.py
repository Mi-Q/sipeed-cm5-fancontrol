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
import configparser
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Dict, List, Optional

DEFAULT_PIN = 13
DEFAULT_FREQ = 50
DEFAULT_POLL_SECONDS = 5
DEFAULT_MIN_DUTY = 25.0
DEFAULT_MIN_TEMP = 45.0
DEFAULT_MAX_TEMP = 60.0

logger = logging.getLogger("sipeed-cm5-fancontrol")


def load_config(
    config_path: str = "/etc/sipeed-cm5-fancontrol/fancontrol.conf",
) -> Dict[str, any]:
    """Load configuration from file.

    Args:
        config_path: Path to configuration file

    Returns:
        Dict with configuration values
    """
    defaults = {
        "mode": "auto",
        "manual_speed": 50,
        "temp_low": DEFAULT_MIN_TEMP,
        "temp_high": DEFAULT_MAX_TEMP,
        "fan_speed_low": DEFAULT_MIN_DUTY,
        "fan_speed_high": 100.0,
        "fan_curve": "exponential",
        "step_zones": "35:0,45:30,55:60,65:100",
        "step_hysteresis": 2.0,
        "fan_min_operating_speed": 10.0,
        "fan_stop_temp": 20.0,
    }

    if not os.path.exists(config_path):
        logger.info("Config file not found, using defaults: mode=auto")
        return defaults

    try:
        config = configparser.ConfigParser()
        # Read as INI-style or simple key=value
        with open(config_path) as f:
            content = f.read()
            # If it doesn't have sections, add a default one
            if not content.strip().startswith("["):
                content = "[DEFAULT]\n" + content
            config.read_string(content)

        section = config["DEFAULT"]
        return {
            "mode": section.get("MODE", "auto").lower(),
            "manual_speed": float(section.get("MANUAL_SPEED", "50")),
            "temp_low": float(section.get("TEMP_LOW", str(DEFAULT_MIN_TEMP))),
            "temp_high": float(section.get("TEMP_HIGH", str(DEFAULT_MAX_TEMP))),
            "fan_speed_low": float(section.get("FAN_SPEED_LOW", str(DEFAULT_MIN_DUTY))),
            "fan_speed_high": float(section.get("FAN_SPEED_HIGH", "100")),
            "fan_curve": section.get("FAN_CURVE", "exponential").lower(),
            "step_zones": section.get("STEP_ZONES", "35:0,45:30,55:60,65:100"),
            "step_hysteresis": float(section.get("STEP_HYSTERESIS", "2")),
            "fan_min_operating_speed": float(section.get("FAN_MIN_OPERATING_SPEED", "10")),
            "fan_stop_temp": float(section.get("FAN_STOP_TEMP", "20")),
        }
    except Exception as e:
        logger.warning("Error loading config file: %s, using defaults", e)
        return defaults


class StatusHTTPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for status endpoint."""

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass

    def do_GET(self):
        """Handle GET requests."""
        if self.path == "/status" or self.path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # Get status from server's fan_controller reference
            status = self.server.fan_controller.get_status()
            self.wfile.write(json.dumps(status, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()


class StatusServer:
    """HTTP server for exposing fan controller status."""

    def __init__(self, fan_controller, port: int = 8081, bind: str = "0.0.0.0"):
        self.fan_controller = fan_controller
        self.port = port
        self.bind = bind
        self.server = None
        self.thread = None

    def start(self):
        """Start the HTTP server in a background thread."""
        # Enable SO_REUSEADDR to allow quick restart without waiting for TIME_WAIT
        HTTPServer.allow_reuse_address = True
        self.server = HTTPServer((self.bind, self.port), StatusHTTPHandler)
        self.server.fan_controller = self.fan_controller
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        logger.info("Status server started on %s:%d", self.bind, self.port)

    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            self.server.shutdown()
            logger.info("Status server stopped")


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
        logger.info("[DummyPWM] start duty=%.1f on pin %s freq %s", duty, self.pin, self.freq)

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


class LGPIOWrapper:
    """Wrapper for lgpio to provide RPi.GPIO-compatible interface.

    lgpio is the modern GPIO library for Raspberry Pi that works in containers
    on RPi 5/CM5. This wrapper provides compatibility with the RPi.GPIO API.
    """

    BCM = "BCM"
    OUT = "OUT"

    def __init__(self):
        """Initialize lgpio wrapper."""
        self._chip = None
        self._pwm_instances = {}

    def setmode(self, m):
        """Set GPIO mode (BCM/BOARD).

        Args:
            m (str): GPIO mode identifier
        """
        import lgpio

        if self._chip is None:
            # Open GPIO chip (gpiochip4 for RPi 5/CM5)
            self._chip = lgpio.gpiochip_open(4)
        logger.info("[lgpio] setmode %s (chip opened)", m)

    def setup(self, pin, mode):
        """Configure GPIO pin mode.

        Args:
            pin (int): GPIO pin number (BCM numbering)
            mode (str): Pin mode (IN/OUT)
        """
        import lgpio

        if self._chip is None:
            self._chip = lgpio.gpiochip_open(4)

        if mode == self.OUT:
            lgpio.gpio_claim_output(self._chip, pin)
            logger.info("[lgpio] setup pin=%s mode=%s", pin, mode)

    def pwm(self, pin, freq):
        """Create PWM instance for given pin.

        Args:
            pin (int): GPIO pin number
            freq (int): PWM frequency in Hz

        Returns:
            LGPIOPWMWrapper: PWM controller instance
        """
        pwm = LGPIOPWMWrapper(self._chip, pin, freq)
        self._pwm_instances[pin] = pwm
        return pwm

    # Alias for RPi.GPIO compatibility
    PWM = pwm

    def cleanup(self):
        """Clean up GPIO resources."""
        import lgpio

        # Stop all PWM instances
        for pwm in self._pwm_instances.values():
            pwm.stop()
        # Close chip
        if self._chip is not None:
            lgpio.gpiochip_close(self._chip)
            self._chip = None
        logger.info("[lgpio] cleanup")


class LGPIOPWMWrapper:
    """Wrapper for lgpio PWM to provide RPi.GPIO.PWM-compatible interface."""

    def __init__(self, chip, pin, freq):
        """Initialize PWM wrapper.

        Args:
            chip: lgpio chip handle
            pin (int): GPIO pin number
            freq (int): PWM frequency in Hz
        """
        self._chip = chip
        self._pin = pin
        self._freq = freq
        self._duty_cycle = 0
        self._running = False

    def start(self, duty_cycle):
        """Start PWM with given duty cycle.

        Args:
            duty_cycle (float): Duty cycle percentage (0-100)
        """
        import lgpio

        self._duty_cycle = duty_cycle
        # Start PWM using tx_pwm (hardware PWM on supported pins)
        # For GPIO 13, we can use hardware PWM channel
        try:
            lgpio.tx_pwm(self._chip, self._pin, self._freq, duty_cycle)
            self._running = True
            logger.debug("[lgpio] PWM started on pin %s: freq=%sHz duty=%.1f%%", self._pin, self._freq, duty_cycle)
        except Exception as e:
            logger.error("[lgpio] PWM start failed: %s", e)

    def ChangeDutyCycle(self, duty_cycle):
        """Change PWM duty cycle.

        Args:
            duty_cycle (float): New duty cycle percentage (0-100)
        """
        import lgpio

        if self._running:
            self._duty_cycle = duty_cycle
            try:
                lgpio.tx_pwm(self._chip, self._pin, self._freq, duty_cycle)
                logger.debug("[lgpio] PWM duty cycle changed to %.1f%%", duty_cycle)
            except Exception as e:
                logger.error("[lgpio] PWM duty cycle change failed: %s", e)

    def stop(self):
        """Stop PWM output."""
        import lgpio

        if self._running:
            try:
                lgpio.tx_pwm(self._chip, self._pin, self._freq, 0)
                self._running = False
                logger.debug("[lgpio] PWM stopped on pin %s", self._pin)
            except Exception as e:
                logger.error("[lgpio] PWM stop failed: %s", e)


def import_gpio(dry_run: bool):
    """Import GPIO module or return dummy implementation.

    Args:
        dry_run (bool): If True, always return dummy implementation

    Returns:
        module: RPi.GPIO module, LGPIOWrapper, or DummyGPIO instance

    Note:
        When not in dry-run mode:
        - In Kubernetes: prefers lgpio (works in containers on RPi 5/CM5)
        - In systemd: prefers RPi.GPIO (traditional approach)
    """
    if dry_run:
        return DummyGPIO()

    # Detect if running in Kubernetes
    in_kubernetes = os.path.exists("/var/run/secrets/kubernetes.io/serviceaccount")

    if in_kubernetes:
        # In Kubernetes: prefer lgpio (works in containers on RPi 5/CM5)
        try:
            import lgpio  # noqa: F401

            logger.info("Kubernetes environment detected, using lgpio")
            return LGPIOWrapper()
        except ImportError:
            logger.warning("lgpio not available in Kubernetes environment, falling back to RPi.GPIO")

    # Try RPi.GPIO (works in systemd on all RPi models)
    try:
        import RPi.GPIO as GPIO

        # Test if GPIO can actually be initialized
        try:
            GPIO.setmode(GPIO.BCM)
            logger.info("Using RPi.GPIO")
            return GPIO
        except (RuntimeError, ValueError) as e:
            logger.warning("RPi.GPIO cannot access hardware (%s), falling back to DummyGPIO", e)
            return DummyGPIO()
    except ImportError:
        logger.warning("RPi.GPIO not available, falling back to DummyGPIO (dry-run mode)")
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
        out = subprocess.check_output(cmd_vcgencmd, stderr=subprocess.DEVNULL, timeout=timeout + 2)
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
            out = subprocess.check_output(cmd_sysfs, stderr=subprocess.DEVNULL, timeout=timeout + 2)
            s = out.decode("utf-8").strip()
            if s:
                return float(s) / 1000.0
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            return None
    return None


def read_remote_temp_http(url: str, timeout: int = 5) -> Optional[float]:
    """Read temperature via HTTP endpoint that returns a plain number (C).

    Minimal implementation using curl to avoid new Python dependencies.
    Automatically constructs full URL if only hostname/IP is provided.

    Args:
        url: HTTP endpoint URL or hostname (e.g., 'http://node2:8080/temp' or 'node2')
        timeout: Request timeout in seconds

    Returns:
        Optional[float]: Temperature in Celsius or None if request fails
    """
    # Construct full URL if only hostname provided
    if not url.startswith("http://") and not url.startswith("https://"):
        url = f"http://{url}:8080/temp"
    elif ":" not in url.split("://", 1)[1]:
        # Has http:// but no port, add default port and path
        url = f"{url}:8080/temp"
    elif not url.endswith("/temp") and not url.endswith("/metrics"):
        # Has host:port but no path
        url = f"{url}/temp"

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
    curve_type: str = "linear",
) -> float:
    """Map temperature to PWM duty cycle with various curve types.

    Args:
        temp_c: Current temperature in Celsius
        min_temp: Temperature at or below which min_duty is used
        max_temp: Temperature at or above which max_duty is used
        min_duty: Minimum duty cycle percentage (0-100)
        max_duty: Maximum duty cycle percentage (0-100)
        curve_type: Type of curve - "linear", "exponential", or "step"

    Returns:
        PWM duty cycle percentage (0-100)

    Curve Types:
        - linear: Proportional increase (original behavior)
        - exponential: Slow increase at low temps, rapid at high temps (quieter)
        - step: Not used here, handled separately with hysteresis
    """
    if temp_c <= min_temp:
        return float(min_duty)
    if temp_c >= max_temp:
        return float(max_duty)

    # Normalize temperature to 0-1 range
    ratio = (temp_c - min_temp) / (max_temp - min_temp)

    if curve_type == "exponential":
        # Quadratic curve: fan speed increases with square of temperature ratio
        # This keeps the fan quieter at moderate temps while still providing
        # aggressive cooling at high temps
        ratio = ratio**2
    elif curve_type == "linear":
        # Linear interpolation (original behavior)
        pass
    else:
        # Unknown curve type, fall back to linear
        logger.warning("Unknown fan curve type '%s', using linear", curve_type)

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
        config_path: Optional[str] = None,
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

        # Kubernetes discovery settings
        self.k8s_discovery_enabled = False
        self.k8s_static_peers: List[str] = []
        self.k8s_namespace: Optional[str] = None
        self.k8s_label_selector: str = "app.kubernetes.io/name=sipeed-temp-exporter"
        self.k8s_port: int = 8080
        self._discovery_counter = 0
        self._discovery_interval = 12  # Rediscover every 12 polling cycles (1 minute with 5s polls)

        # Load config file
        self.config_path = config_path or "/etc/sipeed-cm5-fancontrol/fancontrol.conf"
        self.config = load_config(self.config_path)
        self.mode = self.config["mode"]
        self.manual_speed = self.config["manual_speed"]

        # Initialize fan curve attributes (used in auto mode)
        self.max_duty = 100.0
        self.fan_curve = "linear"
        self.step_zones = []
        self.step_hysteresis = 0
        self.current_step_index = 0
        self.fan_min_operating_speed = 10.0
        self.fan_stop_temp = 20.0

        # Override temperature thresholds from config if in auto mode
        if self.mode == "auto":
            self.min_temp = self.config["temp_low"]
            self.max_temp = self.config["temp_high"]
            self.min_duty = self.config["fan_speed_low"]
            self.max_duty = self.config["fan_speed_high"]
            self.fan_curve = self.config["fan_curve"]
            self.fan_min_operating_speed = self.config["fan_min_operating_speed"]
            self.fan_stop_temp = self.config["fan_stop_temp"]

            # Parse step zones for step curve mode
            if self.fan_curve == "step":
                self.step_zones = self._parse_step_zones(self.config["step_zones"])
                self.step_hysteresis = self.config["step_hysteresis"]
                self.current_step_index = 0  # Track current step for hysteresis

        # Status tracking
        self.last_temps = {}
        self.last_aggregate_temp = None
        self.last_result = None

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

    def _parse_step_zones(self, zones_str: str) -> List[tuple]:
        """Parse step zones configuration string.

        Args:
            zones_str: Comma-separated zones in format "temp1:speed1,temp2:speed2,..."

        Returns:
            List of (temperature, speed) tuples sorted by temperature
        """
        zones = []
        try:
            for zone in zones_str.split(","):
                temp_str, speed_str = zone.strip().split(":")
                temp = float(temp_str)
                speed = float(speed_str)
                zones.append((temp, speed))
            zones.sort(key=lambda x: x[0])  # Sort by temperature
            logger.info("Parsed step zones: %s", zones)
        except Exception as e:
            logger.error("Error parsing step zones '%s': %s, using defaults", zones_str, e)
            zones = [(35, 0), (45, 30), (55, 60), (65, 100)]
        return zones

    def _calculate_step_duty(self, temp_c: float) -> float:
        """Calculate duty cycle using step curve with hysteresis.

        Args:
            temp_c: Current temperature in Celsius

        Returns:
            Duty cycle percentage (0-100)
        """
        if not self.step_zones:
            # Fallback to linear if no zones configured
            return temp_to_duty(
                temp_c,
                self.min_temp,
                self.max_temp,
                self.min_duty,
                self.max_duty,
                "linear",
            )

        # Find appropriate zone with hysteresis
        # If temperature is rising, need to exceed zone threshold
        # If temperature is falling, need to fall below (threshold - hysteresis)

        new_index = self.current_step_index

        # Check if we should move to a higher zone (temperature rising)
        for i in range(self.current_step_index + 1, len(self.step_zones)):
            if temp_c >= self.step_zones[i][0]:
                new_index = i

        # Check if we should move to a lower zone (temperature falling)
        for i in range(self.current_step_index - 1, -1, -1):
            if temp_c < (
                self.step_zones[i + 1][0] - self.step_hysteresis if i + 1 < len(self.step_zones) else float("inf")
            ):
                new_index = i
            else:
                break

        self.current_step_index = new_index

        # Return speed for current zone, or first zone if below all thresholds
        if temp_c < self.step_zones[0][0]:
            return float(self.step_zones[0][1])

        return float(self.step_zones[self.current_step_index][1])

    def _apply_min_operating_speed(self, duty: float, temp_c: float) -> float:
        """Apply minimum operating speed threshold to prevent dead zone.

        Many fans don't spin below a certain PWM duty cycle (typically 10%).
        This method ensures the fan either stays completely off or runs at
        minimum operating speed or higher, avoiding the dead zone.

        Args:
            duty: Calculated duty cycle percentage (0-100)
            temp_c: Current temperature in Celsius

        Returns:
            Adjusted duty cycle percentage (0-100)
        """
        # If duty is already at or above minimum operating speed, return as-is
        if duty >= self.fan_min_operating_speed:
            return duty

        # If duty is 0 or temperature is at/below stop temp, keep fan off
        if duty == 0 or temp_c <= self.fan_stop_temp:
            return 0.0

        # Duty is in dead zone (0 < duty < min_operating_speed) and temp > stop_temp
        # Snap up to minimum operating speed
        logger.debug(
            "Duty %.1f%% in dead zone, snapping to minimum %.1f%% (temp=%.1f°C > stop_temp=%.1f°C)",
            duty,
            self.fan_min_operating_speed,
            temp_c,
            self.fan_stop_temp,
        )
        return self.fan_min_operating_speed

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
            # Some GPIO backends may not implement 'stop'; safe to ignore.
            pass
        try:
            self.GPIO.cleanup()
        except AttributeError:
            # Some GPIO backends may not implement 'cleanup'; safe to ignore.
            pass
        self._running = False
        logger.info("Fan controller stopped")

    def get_status(self) -> dict:
        """Get current status of fan controller.

        Returns:
            dict: Status information including temperatures and duty cycle
        """
        status = {
            "mode": self.mode,
            "running": self._running,
            "fan_duty_percent": self.last_duty,
            "temperatures": self.last_temps,
            "aggregate_method": self.aggregate,
            "aggregate_temp_celsius": self.last_aggregate_temp,
            "config": {
                "min_temp": self.min_temp,
                "max_temp": self.max_temp,
                "min_duty": self.min_duty,
                "manual_speed": self.manual_speed if self.mode == "manual" else None,
                "fan_curve": getattr(self, "fan_curve", "linear"),
                "max_duty": getattr(self, "max_duty", 100.0),
            },
            "peers": self.peers,
            "remote_method": self.remote_method,
        }
        return status

    def _rediscover_peers(self) -> None:
        """Rediscover Kubernetes peers if discovery is enabled.

        This method is called periodically to update the peer list
        when pods are restarted or rescheduled with new IPs.
        """
        if not self.k8s_discovery_enabled:
            return

        try:
            from k8s_discovery import get_peers_with_discovery

            all_peers = get_peers_with_discovery(
                static_peers=self.k8s_static_peers,
                enable_k8s_discovery=True,
                k8s_namespace=self.k8s_namespace,
                k8s_label_selector=self.k8s_label_selector,
                k8s_port=self.k8s_port,
            )

            # Only log if peers changed
            if set(all_peers) != set(self.peers):
                logger.info("Peer list updated: %d peers discovered", len(all_peers))
                self.peers = all_peers
        except Exception as e:
            logger.warning("Failed to rediscover peers: %s", e)

    def run_once(self) -> Optional[dict]:
        """Execute one iteration of temperature check and fan control.

        Returns:
            Optional[dict]: Dictionary with temperatures and duty cycle,
                or None on failure
        """
        # Periodically rediscover Kubernetes peers (every ~1 minute)
        if self.k8s_discovery_enabled:
            self._discovery_counter += 1
            if self._discovery_counter >= self._discovery_interval:
                self._rediscover_peers()
                self._discovery_counter = 0

        # Check if mode is manual
        if self.mode == "manual":
            duty = self.manual_speed
            # Apply manual duty cycle
            if self.last_duty is None or abs(duty - self.last_duty) >= 1.0:
                try:
                    self.pwm.ChangeDutyCycle(duty)
                    logger.info("Manual mode: duty %.1f%%", duty)
                except AttributeError as e:
                    logger.warning("Failed to set duty cycle: %s", e)
            self.last_duty = duty
            self.last_temps = {}
            self.last_aggregate_temp = None
            return {"mode": "manual", "duty": duty}

        # Auto mode: read temperature and adjust fan speed
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
                        (read_remote_temp_ssh if self.remote_method == "ssh" else read_remote_temp_http),
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

        # Store temperatures for status endpoint
        self.last_temps = temps

        # compute aggregate temperature used to decide fan speed
        valid_temps = [v for v in temps.values() if v is not None]
        if not valid_temps:
            logger.error("No valid temperature readings (local or peers)")
            return None

        if self.aggregate == "max":
            t = max(valid_temps)
        else:
            t = sum(valid_temps) / len(valid_temps)

        self.last_aggregate_temp = t

        # Calculate duty based on configured fan curve
        if self.fan_curve == "step":
            duty = self._calculate_step_duty(t)
        else:
            duty = temp_to_duty(
                t,
                self.min_temp,
                self.max_temp,
                self.min_duty,
                self.max_duty,
                self.fan_curve,
            )

        # clamp
        duty = max(self.min_duty, min(100.0, duty))

        # Apply minimum operating speed threshold to avoid dead zone
        duty = self._apply_min_operating_speed(duty, t)

        # Log all individual temperatures with current fan duty cycle
        temp_strs = [f"{host}={temp:.1f}°C" if temp else f"{host}=N/A" for host, temp in temps.items()]
        current_duty_str = f"{self.last_duty:.1f}%" if self.last_duty is not None else "N/A"
        logger.info("Temperatures: %s | Fan: %s", ", ".join(temp_strs), current_duty_str)

        # apply small hysteresis: only change if >1% difference
        if self.last_duty is None or abs(duty - self.last_duty) >= 1.0:
            try:
                # real PWM ChangeDutyCycle or Dummy implementation
                self.pwm.ChangeDutyCycle(duty)
                logger.info(
                    "Aggregate temp (method=%s, curve=%s): %.1f°C -> Fan: %.1f%%",
                    self.aggregate,
                    self.fan_curve,
                    t,
                    duty,
                )
            except AttributeError as e:
                logger.warning("Failed to set duty cycle: %s", e)
        self.last_duty = duty
        result = {"aggregated_temp": t, "duty": duty, "per_host": temps}
        self.last_result = result
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
    p = argparse.ArgumentParser(description="Sipeed CM5 fan controller for Raspberry Pi")
    p.add_argument("--pin", type=int, default=DEFAULT_PIN, help="GPIO pin (BCM) to use")
    p.add_argument("--freq", type=int, default=DEFAULT_FREQ, help="PWM frequency")
    p.add_argument("--poll", type=int, default=DEFAULT_POLL_SECONDS, help="Poll interval seconds")
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
    p.add_argument("--min-duty", type=float, default=DEFAULT_MIN_DUTY, help="Minimum duty percent")
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
    p.add_argument("--remote-timeout", type=int, default=5, help="Timeout seconds for remote polls")
    p.add_argument(
        "--status-port",
        type=int,
        default=8081,
        help="HTTP port for status endpoint (0 to disable)",
    )
    p.add_argument(
        "--status-bind",
        type=str,
        default="0.0.0.0",
        help="Bind address for status HTTP server",
    )
    p.add_argument(
        "--k8s-discovery",
        action="store_true",
        help="Enable Kubernetes auto-discovery of temp exporter pods",
    )
    p.add_argument(
        "--k8s-namespace",
        type=str,
        default=None,
        help="Kubernetes namespace for discovery (default: current namespace)",
    )
    p.add_argument(
        "--k8s-label-selector",
        type=str,
        default="app.kubernetes.io/name=sipeed-temp-exporter",
        help="Label selector for discovering temp exporter pods",
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

    # Parse static peers from command line or config file
    static_peers = []
    if args.peers:
        static_peers = [p.strip() for p in args.peers.split(",") if p.strip()]
    else:
        # If no --peers argument, try to load from config file
        peers_config_file = "/etc/sipeed-cm5-fancontrol/peers.conf"
        if os.path.exists(peers_config_file):
            try:
                with open(peers_config_file, "r") as f:
                    peers_content = f.read().strip()
                    if peers_content:
                        static_peers = [p.strip() for p in peers_content.split(",") if p.strip()]
                        logger.info(
                            "Loaded %d peers from %s",
                            len(static_peers),
                            peers_config_file,
                        )
            except Exception as e:
                logger.warning("Failed to read peers config file %s: %s", peers_config_file, e)

    # Add Kubernetes discovery if enabled
    if args.k8s_discovery:
        try:
            from k8s_discovery import get_peers_with_discovery

            # Enable periodic rediscovery
            controller.k8s_discovery_enabled = True
            controller.k8s_static_peers = static_peers
            controller.k8s_namespace = args.k8s_namespace
            controller.k8s_label_selector = args.k8s_label_selector
            controller.k8s_port = 8080

            # Do initial discovery
            all_peers = get_peers_with_discovery(
                static_peers=static_peers,
                enable_k8s_discovery=True,
                k8s_namespace=args.k8s_namespace,
                k8s_label_selector=args.k8s_label_selector,
                k8s_port=8080,
            )
            controller.peers = all_peers
            logger.info("Using Kubernetes discovery: %d total peers (will rediscover every ~1 min)", len(all_peers))
        except ImportError as e:
            logger.warning("Kubernetes discovery failed: %s", e)
            logger.warning("Falling back to static peers")
            controller.peers = static_peers
    else:
        controller.peers = static_peers

    controller.remote_method = args.remote_method
    controller.aggregate = args.aggregate
    controller.remote_timeout = args.remote_timeout

    # Start status HTTP server if enabled
    status_server = None
    if args.status_port > 0:
        status_server = StatusServer(controller, port=args.status_port, bind=args.status_bind)
        status_server.start()

    try:
        controller.run_loop()
    finally:
        if status_server:
            status_server.stop()


if __name__ == "__main__":
    main()
