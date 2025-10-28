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
  - Provides local temperature on HTTP endpoint `:8000/temp`
  - Provides Prometheus metrics on `:8000/metrics`
  - **Only install `sipeed-temp-exporter.service` on these nodes**

## Files
- `fan_control.py` - Main fan controller script
- `temp_exporter.py` - Temperature exporter HTTP service
- `sipeed-cm5-fancontrol.service` - Systemd service for fan controller
- `sipeed-temp-exporter.service` - Systemd service for temperature exporter
- `install.sh` - Interactive installation script
- `tests/` - Unit tests for fan control logic

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

### Option 2: Clone Repository

Clone the repository and run the installer:

```bash
# Clone the repository
git clone https://github.com/Mi-Q/sipeed-cm5-fancontrol.git
cd sipeed-cm5-fancontrol/deploy-systemd

# Run the installer
sudo ./install.sh
```

---

The installation script will:
1. Ask if this is a **Fan Control Node** (Slot 1) or **Temperature Provider Node** (Slots 2-4)
2. For Fan Control Node: prompt for peer node addresses and polling method (HTTP/SSH)
3. Install the appropriate service to `/opt/sipeed-fancontrol/`
4. Configure and start the systemd service automatically

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

The services run as root to allow GPIO access. You can modify the service files to adjust:
- Paths to Python scripts
- Command line arguments
- Restart behavior
- Dependencies

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