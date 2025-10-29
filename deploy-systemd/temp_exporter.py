#!/usr/bin/env python3
"""Minimal HTTP temperature exporter for Sipeed CM5 nodes.

Copyright (c) 2025 Michael Kuppinger (Mi-Q)
Contact: michael@kuppinger.eu
Licensed under the MIT License - see LICENSE file for details.

Version: 0.2.0

Endpoints:
- GET /temp    -> returns plain text temperature in Celsius (e.g. '42.5')
- GET /metrics -> returns a Prometheus-style metric `node_temperature_celsius`.

This server is intentionally dependency-free and uses the stdlib http.server module.
"""
import argparse
import http.server
import logging
import os
import re
import socketserver
import subprocess
from typing import Optional

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


class TempHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for temperature metrics.

    Provides two endpoints:
    - /temp: Returns plain text temperature in Celsius
    - /metrics: Returns Prometheus-style metrics
    """

    def do_GET(self):  # pylint: disable=invalid-name
        """Handle GET requests for temperature metrics."""
        if self.path == "/temp":
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

        if self.path == "/metrics":
            t = read_cpu_temp()
            if t is None:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"# error reading temp\n")
                return
            metric = "# HELP node_temperature_celsius Node CPU temperature in Celsius\n"
            metric += "# TYPE node_temperature_celsius gauge\n"
            metric += f"node_temperature_celsius {t:.3f}\n"
            body = metric.encode("utf-8")
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
    p.add_argument("--port", type=int, default=8080, help="Port to listen on")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    with socketserver.TCPServer((args.bind, args.port), TempHandler) as httpd:
        logger.info("Temperature exporter listening on %s:%d", args.bind, args.port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down")


if __name__ == "__main__":
    main()
