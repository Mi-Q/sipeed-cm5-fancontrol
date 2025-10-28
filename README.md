# Sipeed CM5 Fan Controller

This project provides a small Python daemon to control the fan on a Sipeed CM5 module (Raspberry Pi) by mapping CPU temperature to PWM duty cycle.

Key behavior:
- Minimum fan duty is 25% by default (keeps idle temps ~35-45°C)
- 100% fan duty when CPU reaches the configured `--max-temp` (default 60°C)
- Linear interpolation between `--min-temp` (default 45°C) and `--max-temp` (default 60°C)

Files:
- `fan_control.py` — main script (has dry-run and simulate-temp options)
- `sipeed-cm5-fancontrol.service` — example systemd unit (adjust the path before enabling)
- `tests/test_mapping.py` and `run_tests.py` — basic unit tests for the mapping function

Quick usage
------------

Dry-run (safe on non-RPi systems):

```bash
python3 fan_control.py --dry-run --simulate-temp 50
```

Run on Raspberry Pi (use sudo or run as root):

```bash
sudo python3 fan_control.py
```

Installing as a systemd service
-------------------------------
1. Copy `sipeed-cm5-fancontrol.service` to `/etc/systemd/system/sipeed-cm5-fancontrol.service` and edit `ExecStart` to the absolute path of `fan_control.py`.
2. Reload systemd and enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now sipeed-cm5-fancontrol.service
```

Testing
-------
Run the included unit tests (uses unittest):

```bash
python3 run_tests.py
```

Notes
-----
- The script prefers `/usr/bin/vcgencmd measure_temp` when available and falls back to `/sys/class/thermal/thermal_zone0/temp`.
- Tweak `--min-temp`, `--max-temp`, and `--min-duty` to match your thermal profile.
