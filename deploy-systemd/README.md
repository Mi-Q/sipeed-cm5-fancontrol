# Sipeed CM5 Fan Control - systemd Service

This directory contains the systemd service implementation for running the Sipeed CM5 Fan Controller directly on the Raspberry Pi.

## Architecture

The Sipeed NanoCluster has 7 slots with one fan connected to **Slot 1**. The fan control system uses a distributed architecture:

- **Slot 1 (Fan Control Node)**: Runs `fan_control.py` to control the fan based on temperatures from all nodes
  - Reads local temperature directly (no temp exporter service needed)
  - Polls temperatures from peer nodes in other slots (e.g., Slots 2-7)
  - Adjusts fan speed based on aggregated temperatures
  - **Only install `sipeed-cm5-fancontrol.service` on this node**
  
- **Other Slots (Temperature Provider Nodes)**: Run `temp_exporter.py` to expose temperature via HTTP
  - Provides local temperature on HTTP endpoint `:8080/temp`
  - Provides Prometheus metrics on `:8080/metrics`
  - **Only install `sipeed-temp-exporter.service` on these nodes**

## Files
- `fan_control.py` - Main fan controller script with manual/auto mode support
- `fan_control.conf` - Configuration file for fan control modes and thresholds
- `temp_exporter.py` - Temperature exporter HTTP service
- `sipeed-cm5-fancontrol.service` - Systemd service for fan controller
- `sipeed-temp-exporter.service` - Systemd service for temperature exporter
- `install.sh` - Interactive installation script with upgrade support
- `uninstall.sh` - Safe uninstallation script
- `tests/` - Comprehensive unit tests (98% code coverage)

## Quick Installation

### Option 1: One-Line Install (Recommended)

Download and run the installer directly from the latest release:

```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/main/deploy-systemd/install.sh | sudo bash
```

Or from a specific release tag:

```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/v1.0.0/deploy-systemd/install.sh | sudo bash
```

**Upgrade existing installation:**

```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/main/deploy-systemd/install.sh | sudo bash -s -- --reinstall
```

Or if you have the script locally:

```bash
sudo ./install.sh --reinstall
```

### Option 2: Clone Repository

Clone the repository and run the installer:

```bash
# Clone the repository
git clone https://github.com/Mi-Q/sipeed-cm5-fancontrol.git
cd sipeed-cm5-fancontrol/deploy-systemd

# Run the installer
sudo ./install.sh

# Or use --reinstall flag to upgrade
sudo ./install.sh --reinstall
```

---

The installation script will:
1. Check for existing installations and offer to reinstall/reconfigure
2. Ask if this is a **Fan Control Node** (Slot 1) or **Temperature Provider Node** (Slots 2-7)
3. For Fan Control Node: prompt for peer node addresses and polling method (HTTP/SSH)
4. Install files to `/opt/sipeed-fancontrol/`
5. Install configuration file to `/etc/sipeed-fancontrol.conf` (fan control only)
6. Configure and start the systemd service automatically

### Example Setup

**On Slot 1 (Fan Control Node):**
```bash
sudo ./install.sh
# Select option 1 (Fan Control Node)
# Enter peers: node2,node3,node4,node5,node6,node7  (hostname or use IPs: 192.168.1.102,192.168.1.103,...)
# Select HTTP method (option 1)
```

**On Other Slots (Temperature Provider Nodes):**
```bash
sudo ./install.sh
# Select option 2 (Temperature Provider Node)
# Access temperature at: http://<node-ip>:8080/temp
# Access metrics at: http://<node-ip>:8080/metrics
```

## Manual Installation

If you prefer manual installation, clone the repository first and then:

1. Install the systemd services:
   ```bash
   # On the Raspberry Pi
   sudo mkdir -p /opt/sipeed-fancontrol
   sudo cp fan_control.py temp_exporter.py /opt/sipeed-fancontrol/
   sudo cp sipeed-cm5-fancontrol.service sipeed-temp-exporter.service /etc/systemd/system/
   sudo systemctl daemon-reload
   ```

2. Start and enable the appropriate service:
   
   **For Fan Control Node (Slot 1):**
   ```bash
   # Edit service file to add --peers argument if needed
   sudo systemctl enable --now sipeed-cm5-fancontrol.service
   ```
   
   **For Temperature Provider Nodes (Other Slots):**
   ```bash
   sudo systemctl enable --now sipeed-temp-exporter.service
   ```

## Configuration

### Fan Control Modes

The fan controller supports two modes via `/etc/sipeed-fancontrol.conf`:

**Auto Mode (Default):** Automatically adjusts fan speed based on temperature
```bash
MODE=auto
TEMP_LOW=40       # Temperature (°C) for minimum fan speed
TEMP_HIGH=70      # Temperature (°C) for maximum fan speed
FAN_SPEED_LOW=30  # Minimum fan speed (%)
FAN_SPEED_HIGH=100 # Maximum fan speed (%)
```

**Manual Mode:** Fixed fan speed percentage
```bash
MODE=manual
MANUAL_SPEED=75   # Fixed fan speed (0-100%)
```

To change modes, edit the config file and restart the service:
```bash
sudo nano /etc/sipeed-fancontrol.conf
sudo systemctl restart sipeed-cm5-fancontrol.service
```

### Service Configuration

The services run as root to allow GPIO access. You can modify the service files to adjust:
- Paths to Python scripts
- Command line arguments (for fan control: `--peers`, `--remote-method`)
- Restart behavior
- Dependencies

Service files are located at:
- `/etc/systemd/system/sipeed-cm5-fancontrol.service`
- `/etc/systemd/system/sipeed-temp-exporter.service`

After modifying service files:
```bash
sudo systemctl daemon-reload
sudo systemctl restart <service-name>
```

## Uninstallation

To remove the installed services:

```bash
# If you have the repository cloned
cd sipeed-cm5-fancontrol/deploy-systemd
sudo ./uninstall.sh

# Or download and run directly
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/main/deploy-systemd/uninstall.sh | sudo bash
```

The uninstall script will:
1. Detect all installed services
2. Stop and disable them
3. Remove service files from `/etc/systemd/system/`
4. Remove installation directory `/opt/sipeed-fancontrol/`
5. Optionally remove configuration file `/etc/sipeed-fancontrol.conf`

## Testing

To run the unit tests:
```bash
python3 -m pytest tests/
```

## Logs

View service logs using:
```bash
sudo journalctl -u sipeed-cm5-fancontrol.service
sudo journalctl -u sipeed-temp-exporter.service
```

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.