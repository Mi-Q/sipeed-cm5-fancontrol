#!/usr/bin/env python3
"""Enhanced metrics exporter for Sipeed CM5 nodes.

Copyright (c) 2025 Michael Kuppinger (Mi-Q)
Contact: michael@kuppinger.eu
Licensed under the MIT License - see LICENSE file for details.

Version: 0.4.0

Endpoints:
- GET /temp    -> returns plain text CPU temperature in Celsius (e.g. '42.5')
- GET /temps   -> returns JSON with all temperature sensors
- GET /metrics -> returns comprehensive Prometheus metrics

Metrics include:
- All temperature sensors (CPU, NVMe, RP1 I/O controller)
- Memory usage (total, available, used, cached, buffers)
- CPU load (1min, 5min, 15min)
- Disk usage (per mount point)
- Network I/O (per interface)
- System uptime

This server is intentionally dependency-free and uses the stdlib http.server module.
"""
import argparse
import http.server
import json
import logging
import os
import re
import socketserver
import subprocess
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("temp_exporter")


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
    """Read CPU temperature from sysfs.

    Returns:
        Optional[float]: Temperature in Celsius or None if reading fails
    """
    path = "/sys/class/thermal/thermal_zone0/temp"
    try:
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return float(v) / 1000.0
    except (IOError, ValueError) as e:
        logger.debug("sysfs temp read failed: %s", e)
    return None


def read_cpu_temp() -> Optional[float]:
    """Read CPU temperature using vcgencmd or sysfs fallback.

    Returns:
        Optional[float]: Temperature in Celsius or None if all methods fail
    """
    t = read_temp_vcgencmd()
    if t is not None:
        return t
    return read_temp_sysfs()


def read_hwmon_temp(hwmon_path: str, temp_input: str = "temp1_input") -> Optional[float]:
    """Read temperature from hwmon sysfs.

    Args:
        hwmon_path: Path to hwmon device (e.g., /sys/class/hwmon/hwmon1)
        temp_input: Temperature input file name (default: temp1_input)

    Returns:
        Optional[float]: Temperature in Celsius or None if reading fails
    """
    try:
        path = os.path.join(hwmon_path, temp_input)
        with open(path, "r", encoding="utf-8") as f:
            v = f.read().strip()
            if v:
                return float(v) / 1000.0
    except (IOError, ValueError, FileNotFoundError) as e:
        logger.debug("hwmon temp read failed for %s: %s", hwmon_path, e)
    return None


def find_hwmon_by_name(name: str) -> Optional[str]:
    """Find hwmon device by name.

    Args:
        name: Name to search for (e.g., "nvme", "rp1_adc")

    Returns:
        Optional[str]: Path to hwmon device or None if not found
    """
    hwmon_base = "/sys/class/hwmon"
    if not os.path.exists(hwmon_base):
        return None

    for hwmon_dir in os.listdir(hwmon_base):
        hwmon_path = os.path.join(hwmon_base, hwmon_dir)
        name_file = os.path.join(hwmon_path, "name")
        try:
            with open(name_file, "r", encoding="utf-8") as f:
                device_name = f.read().strip()
                if name.lower() in device_name.lower():
                    return hwmon_path
        except (IOError, FileNotFoundError):
            continue
    return None


def read_nvme_temp() -> Optional[float]:
    """Read NVMe SSD temperature.

    Returns:
        Optional[float]: NVMe composite temperature in Celsius or None
    """
    nvme_hwmon = find_hwmon_by_name("nvme")
    if nvme_hwmon:
        # Try composite temperature first (temp1_input)
        temp = read_hwmon_temp(nvme_hwmon, "temp1_input")
        if temp is not None:
            return temp
    return None


def read_rp1_temp() -> Optional[float]:
    """Read RP1 I/O controller temperature.

    Returns:
        Optional[float]: RP1 temperature in Celsius or None
    """
    rp1_hwmon = find_hwmon_by_name("rp1_adc")
    if rp1_hwmon:
        return read_hwmon_temp(rp1_hwmon, "temp1_input")
    return None


def read_all_temps() -> Dict[str, Optional[float]]:
    """Read all available temperature sensors.

    Returns:
        Dict[str, Optional[float]]: Dictionary of sensor name to temperature
    """
    return {
        "cpu": read_cpu_temp(),
        "nvme": read_nvme_temp(),
        "rp1": read_rp1_temp(),
    }


def read_memory_stats() -> Dict[str, float]:
    """Read memory statistics from /proc/meminfo.

    Returns:
        Dict[str, float]: Memory statistics in bytes
    """
    stats = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith(
                    ("MemTotal:", "MemAvailable:", "MemFree:", "Buffers:", "Cached:", "SwapTotal:", "SwapFree:")
                ):
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        value = float(parts[1]) * 1024  # Convert kB to bytes
                        stats[key] = value
    except (IOError, ValueError) as e:
        logger.debug("Failed to read memory stats: %s", e)
    return stats


def read_load_avg() -> Tuple[float, float, float]:
    """Read system load averages.

    Returns:
        Tuple[float, float, float]: Load averages for 1, 5, and 15 minutes
    """
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as f:
            parts = f.read().split()
            if len(parts) >= 3:
                return float(parts[0]), float(parts[1]), float(parts[2])
    except (IOError, ValueError) as e:
        logger.debug("Failed to read load avg: %s", e)
    return 0.0, 0.0, 0.0


def read_disk_stats() -> List[Dict[str, Any]]:
    """Read disk usage statistics.

    Returns:
        List[Dict]: List of disk statistics per mount point
    """
    stats = []
    try:
        output = subprocess.check_output(["df", "-B1"], stderr=subprocess.DEVNULL).decode("utf-8")  # Output in bytes

        for line in output.split("\n")[1:]:  # Skip header
            parts = line.split()
            if len(parts) >= 6 and parts[5].startswith("/"):
                stats.append(
                    {
                        "device": parts[0],
                        "mountpoint": parts[5],
                        "size": int(parts[1]),
                        "used": int(parts[2]),
                        "available": int(parts[3]),
                        "use_percent": float(parts[4].rstrip("%")),
                    }
                )
    except (subprocess.SubprocessError, ValueError, IndexError) as e:
        logger.debug("Failed to read disk stats: %s", e)
    return stats


def read_network_stats() -> Dict[str, Dict[str, int]]:
    """Read network interface statistics.

    Returns:
        Dict[str, Dict[str, int]]: Network stats per interface
    """
    stats = {}
    try:
        with open("/proc/net/dev", "r", encoding="utf-8") as f:
            for line in f:
                if ":" not in line:
                    continue
                parts = line.split(":")
                if len(parts) != 2:
                    continue

                iface = parts[0].strip()
                if iface in ("lo",):  # Skip loopback
                    continue

                values = parts[1].split()
                if len(values) >= 16:
                    stats[iface] = {
                        "rx_bytes": int(values[0]),
                        "rx_packets": int(values[1]),
                        "rx_errors": int(values[2]),
                        "rx_dropped": int(values[3]),
                        "tx_bytes": int(values[8]),
                        "tx_packets": int(values[9]),
                        "tx_errors": int(values[10]),
                        "tx_dropped": int(values[11]),
                    }
    except (IOError, ValueError, IndexError) as e:
        logger.debug("Failed to read network stats: %s", e)
    return stats


def read_uptime() -> float:
    """Read system uptime in seconds.

    Returns:
        float: System uptime in seconds
    """
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as f:
            return float(f.read().split()[0])
    except (IOError, ValueError, IndexError) as e:
        logger.debug("Failed to read uptime: %s", e)
    return 0.0


class TempHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for metrics.

    Provides endpoints:
    - /temp: Returns plain text CPU temperature in Celsius (backward compatible)
    - /temps: Returns JSON with all temperature sensors
    - /metrics: Returns comprehensive Prometheus-style metrics
    """

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle GET requests for metrics."""
        if self.path == "/temp":
            # Backward compatible endpoint - CPU temperature only
            t = read_cpu_temp()
            if t is None:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"error\n")
                return
            body = f"{t:.3f}\n".encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/temps":
            # JSON endpoint with all temperature sensors
            temps = read_all_temps()
            body = json.dumps(temps, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/metrics":
            # Comprehensive Prometheus metrics
            metrics = []

            # Temperature sensors
            temps = read_all_temps()
            metrics.append("# HELP node_temperature_celsius Node temperature sensors in Celsius")
            metrics.append("# TYPE node_temperature_celsius gauge")
            for sensor, temp in temps.items():
                if temp is not None:
                    metrics.append(f'node_temperature_celsius{{sensor="{sensor}"}} {temp:.3f}')

            # Sensor availability
            metrics.append(
                "# HELP node_temperature_sensor_available Whether a temperature sensor is available (1=yes, 0=no)"
            )
            metrics.append("# TYPE node_temperature_sensor_available gauge")
            for sensor, temp in temps.items():
                available = 1 if temp is not None else 0
                metrics.append(f'node_temperature_sensor_available{{sensor="{sensor}"}} {available}')

            # Memory statistics
            mem_stats = read_memory_stats()
            if mem_stats:
                metrics.append("# HELP node_memory_bytes Memory statistics in bytes")
                metrics.append("# TYPE node_memory_bytes gauge")
                for key, value in mem_stats.items():
                    metric_name = key.lower().replace(":", "")
                    metrics.append(f'node_memory_bytes{{type="{metric_name}"}} {value:.0f}')

            # Load averages
            load1, load5, load15 = read_load_avg()
            metrics.append("# HELP node_load_average System load average")
            metrics.append("# TYPE node_load_average gauge")
            metrics.append(f'node_load_average{{period="1m"}} {load1}')
            metrics.append(f'node_load_average{{period="5m"}} {load5}')
            metrics.append(f'node_load_average{{period="15m"}} {load15}')

            # Disk statistics
            disk_stats = read_disk_stats()
            if disk_stats:
                metrics.append("# HELP node_filesystem_size_bytes Filesystem size in bytes")
                metrics.append("# TYPE node_filesystem_size_bytes gauge")
                metrics.append("# HELP node_filesystem_used_bytes Filesystem used space in bytes")
                metrics.append("# TYPE node_filesystem_used_bytes gauge")
                metrics.append("# HELP node_filesystem_avail_bytes Filesystem available space in bytes")
                metrics.append("# TYPE node_filesystem_avail_bytes gauge")
                metrics.append("# HELP node_filesystem_use_percent Filesystem usage percentage")
                metrics.append("# TYPE node_filesystem_use_percent gauge")
                for disk in disk_stats:
                    labels = f'device="{disk["device"]}",mountpoint="{disk["mountpoint"]}"'
                    metrics.append(f'node_filesystem_size_bytes{{{labels}}} {disk["size"]}')
                    metrics.append(f'node_filesystem_used_bytes{{{labels}}} {disk["used"]}')
                    metrics.append(f'node_filesystem_avail_bytes{{{labels}}} {disk["available"]}')
                    metrics.append(f'node_filesystem_use_percent{{{labels}}} {disk["use_percent"]}')

            # Network statistics
            net_stats = read_network_stats()
            if net_stats:
                metrics.append("# HELP node_network_receive_bytes_total Network received bytes")
                metrics.append("# TYPE node_network_receive_bytes_total counter")
                metrics.append("# HELP node_network_transmit_bytes_total Network transmitted bytes")
                metrics.append("# TYPE node_network_transmit_bytes_total counter")
                metrics.append("# HELP node_network_receive_packets_total Network received packets")
                metrics.append("# TYPE node_network_receive_packets_total counter")
                metrics.append("# HELP node_network_transmit_packets_total Network transmitted packets")
                metrics.append("# TYPE node_network_transmit_packets_total counter")
                metrics.append("# HELP node_network_receive_errors_total Network receive errors")
                metrics.append("# TYPE node_network_receive_errors_total counter")
                metrics.append("# HELP node_network_transmit_errors_total Network transmit errors")
                metrics.append("# TYPE node_network_transmit_errors_total counter")
                for iface, stats in net_stats.items():
                    metrics.append(f'node_network_receive_bytes_total{{interface="{iface}"}} {stats["rx_bytes"]}')
                    metrics.append(f'node_network_transmit_bytes_total{{interface="{iface}"}} {stats["tx_bytes"]}')
                    metrics.append(f'node_network_receive_packets_total{{interface="{iface}"}} {stats["rx_packets"]}')
                    metrics.append(f'node_network_transmit_packets_total{{interface="{iface}"}} {stats["tx_packets"]}')
                    metrics.append(f'node_network_receive_errors_total{{interface="{iface}"}} {stats["rx_errors"]}')
                    metrics.append(f'node_network_transmit_errors_total{{interface="{iface}"}} {stats["tx_errors"]}')

            # System uptime
            uptime = read_uptime()
            metrics.append("# HELP node_uptime_seconds System uptime in seconds")
            metrics.append("# TYPE node_uptime_seconds counter")
            metrics.append(f"node_uptime_seconds {uptime:.0f}")

            body = "\n".join(metrics) + "\n"
            body = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format_str, *args):  # pylint: disable=arguments-differ
        """Override to log via Python logging instead of stderr."""
        logger.info(
            "%s - - [%s] %s",
            self.client_address[0],
            self.log_date_time_string(),
            format_str % args,
        )


def main():
    """Main entry point for the temperature exporter server."""
    p = argparse.ArgumentParser(description="Sipeed CM5 temperature exporter")
    p.add_argument("--bind", default="0.0.0.0", help="Bind address")
    p.add_argument("--port", type=int, default=2505, help="Port to listen on")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Enable SO_REUSEADDR to allow quick restart without waiting for TIME_WAIT
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer((args.bind, args.port), TempHandler) as httpd:
        logger.info("Temperature exporter listening on %s:%d", args.bind, args.port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")


if __name__ == "__main__":
    main()
