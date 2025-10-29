# Sipeed CM5 Fan Control

This project provides a fan controller for Sipeed CM5 modules, with support for both systemd service and Kubernetes (k3s) deployments.

## Hardware Platform

This project was developed for the [Sipeed NanoCluster](https://classic.sipeed.com/nanocluster) ([Wiki](https://wiki.sipeed.com/nanocluster)) with 4 Raspberry Pi Compute Module 5 nodes, each equipped with:
- 8GB RAM
- 64GB eMMC storage
- 512GB NVMe M.2 SSD
- Raspberry Pi OS Lite 64-bit

Limited the project to 4 due to space between the components and airflow - up to 7 would be possible on the Sipeed NanoCluster Board in a minimal setup without additional NVMe M.2 SSD

For k3s cluster setup on the NanoCluster, refer to the [Sipeed k3s Installation Guide](https://wiki.sipeed.com/hardware/en/cluster/NanoCluster/k3s.html).

### k3s on Raspberry Pi - Important Configuration

Before installing k3s on Raspberry Pi, you must enable required cgroups by adding kernel parameters to `/boot/firmware/cmdline.txt` ([reference](https://forums.raspberrypi.com/viewtopic.php?t=365198)):

```
cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory
```

Example configuration:
```
console=serial0,115200 console=tty1 root=PARTUUID=xxxxxxxx-02 rootfstype=ext4 fsck.repair=yes rootwait cfg80211.ieee80211_regdom=DE cgroup_enable=cpuset cgroup_memory=1 cgroup_enable=memory
```

Reboot after making this change for k3s to function properly.

## Project Structure

- `deploy-systemd/` - Systemd service implementation for direct installation on Raspberry Pi
- `deploy-kubernetes/` - Kubernetes deployment using Helm charts for cluster environments

## Features

- **Flexible fan control modes**:
  - **Auto mode**: PWM-based fan control with configurable temperature thresholds
  - **Manual mode**: Fixed fan speed percentage for custom setups
- **Real-time monitoring**:
  - HTTP status endpoint showing all node temperatures and fan duty cycle
  - CLI tool (`cm5fan`) for quick status checks
  - Enhanced logging with individual temperature readings and fan percentage
- **Kubernetes-native deployment**:
  - ConfigMap-based configuration (no manual file creation needed)
  - Automatic peer discovery via Kubernetes API
  - Dynamic pod rediscovery (~1 minute) when pods restart
  - lgpio support for GPIO access in containers on RPi 5/CM5
- **Systemd deployment**:
  - Configuration files in `/etc/sipeed-cm5-fancontrol/` for easy mode switching
  - RPi.GPIO library for traditional GPIO access
  - HTTP-based temperature polling from peer nodes
- Temperature polling from local and remote nodes (HTTP)
- Parallel peer temperature polling for fast aggregation
- Prometheus-compatible metrics endpoint
- Interactive installation with one-line curl support
- Upgrade and uninstall scripts for easy maintenance
- Multi-arch container support (amd64, arm64, arm/v7)
- CI/CD pipeline with comprehensive testing (98% code coverage)
- Pre-commit hooks for code quality (black, isort, flake8)

## Deployment Options

Choose between systemd (traditional) or Kubernetes (container-based) deployment:

| Feature | Systemd | Kubernetes |
|---------|---------|------------|
| Configuration | File-based (`/etc/sipeed-cm5-fancontrol/`) | ConfigMap-based |
| Peer Discovery | Static (configured at install) | Dynamic (auto-discovery) |
| GPIO Library | RPi.GPIO | lgpio (container-compatible) |
| Installation | Interactive installer script | Helm chart |
| Best For | Single-node or simple setups | Cluster environments |

### 1. Systemd Service (Direct on Raspberry Pi)

**Quick Install (One-Line):**
```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/main/deploy-systemd/install.sh | sudo bash
```

The interactive installer will guide you through setting up either:
- **Fan Control Node** (Slot 1) - Controls the fan based on all node temperatures
  - Supports auto mode (temperature-based) or manual mode (fixed speed)
  - Configure via `/etc/sipeed-cm5-fancontrol/fancontrol.conf` after installation
- **Temperature Provider Node** (Other Slots) - Exposes temperature via HTTP
  - Provides temperature at `:8080/temp` and metrics at `:8080/metrics`

**Upgrade existing installation:**
```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/main/deploy-systemd/install.sh | sudo bash -s -- --reinstall
```

**📖 For detailed documentation, see [deploy-systemd/README.md](./deploy-systemd/README.md)**

Includes:
- Architecture and hardware setup
- Installation options and upgrade guide
- Configuration modes (auto/manual)
- Fan curves and temperature thresholds
- CLI tools and monitoring
- Troubleshooting guide

### 2. Kubernetes Deployment (k3s)

**Quick Install:**
```bash
cd deploy-kubernetes
./install.sh sipeed-cm5-fancontrol
```

**📖 For detailed documentation, see [deploy-kubernetes/README.md](./deploy-kubernetes/README.md)**

Includes:
- Helm chart installation and upgrades
- ConfigMap-based configuration
- DaemonSets vs Deployments explanation
- Pod management (start/stop/pause)
- Automatic peer rediscovery
- Hardware access with lgpio
- Monitoring and troubleshooting

## Development

### Versioning

This project follows [Semantic Versioning](https://semver.org/):
- **MAJOR** version for incompatible API changes
- **MINOR** version for backwards-compatible functionality additions
- **PATCH** version for backwards-compatible bug fixes

See [CHANGELOG.md](CHANGELOG.md) for version history and release notes.

### Prerequisites
- Python 3.11+
- pytest for running tests
- For k3s: Helm 3.x, kubectl
- For containers: Docker with buildx

### Testing & Linting
The project uses:
- pytest for unit testing
- flake8 for style checking
- pylint for code analysis
- black for code formatting
- isort for import sorting

Run the test suite:
```bash
python -m pytest tests/
```

### CI/CD
GitHub Actions workflow handles:
- Code linting and testing
- Multi-arch container builds
- Container publishing to GitHub Container Registry

## Author

**Michael Kuppinger (Mi-Q)**
- Email: michael@kuppinger.eu
- LinkedIn: [mkuppinger](https://www.linkedin.com/in/mkuppinger/)
- GitHub: [@Mi-Q](https://github.com/Mi-Q)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

