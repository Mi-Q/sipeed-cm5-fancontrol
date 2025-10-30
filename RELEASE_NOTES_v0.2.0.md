# Release v0.2.0 - First Production-Ready Release

This is the first production-ready release of Sipeed CM5 Fan Control with comprehensive features for both systemd and Kubernetes deployments.

## 🎉 Highlights

- **Complete Kubernetes deployment** with Helm charts and ConfigMap configuration
- **Automatic GPIO library selection**: lgpio for containers, RPi.GPIO for systemd
- **Dynamic peer discovery** and rediscovery in Kubernetes (~1 min interval)
- **Enhanced monitoring** with fan duty cycle logging
- **Comprehensive documentation** and examples
- **98% test coverage** with extensive unit tests
- **CI/CD optimizations** for selective image builds

## 📦 Installation

### Systemd (Quick Install)
```bash
curl -sSL https://raw.githubusercontent.com/Mi-Q/sipeed-cm5-fancontrol/v0.2.0/deploy-systemd/install.sh | sudo bash
```

### Kubernetes
```bash
git clone https://github.com/Mi-Q/sipeed-cm5-fancontrol.git
cd sipeed-cm5-fancontrol/deploy-kubernetes
./install.sh sipeed-cm5-fancontrol
```

## ✨ New Features

### Kubernetes ConfigMap Configuration
- Fan controller settings managed via Kubernetes ConfigMap
- All configuration values customizable via Helm `values.yaml`
- Easy updates with `helm upgrade --set` commands
- No need for `peers.conf` - automatic peer discovery

### Automatic GPIO Library Detection
- **Kubernetes**: Uses `lgpio` library (works in containers on RPi 5/CM5)
- **Systemd**: Uses `RPi.GPIO` library (traditional approach)
- Automatic detection based on environment
- Seamless hardware GPIO access in both environments

### Enhanced Logging
- Temperature logs now include current fan duty cycle percentage
- Format: `Temperatures: local=40.2°C, peer1=34.8°C | Fan: 45.0%`
- Complete visibility of fan controller operation

### Automatic Peer Rediscovery
- Fan controller rediscovers temperature exporter pods every ~1 minute
- Handles pod restarts with new IP addresses gracefully
- Logs "Peer list updated" when changes detected

### CI/CD Optimization
- Docker images only build when relevant files change
- Faster CI runs for documentation-only changes
- Reduced container registry API usage

## 📚 Documentation

- [README.md](README.md) - Project overview and quick start
- [deploy-systemd/README.md](deploy-systemd/README.md) - Systemd deployment guide
- [deploy-kubernetes/README.md](deploy-kubernetes/README.md) - Kubernetes deployment guide
- [CHANGELOG.md](CHANGELOG.md) - Detailed change history

## 🐛 Bug Fixes

- Fixed "Address already in use" errors during reinstallation
- Improved installation script reliability
- Better error handling for GPIO access

## 🔧 Technical Details

### Supported Platforms
- Raspberry Pi CM5 with Raspberry Pi OS Lite 64-bit
- Kubernetes/k3s on ARM64 architecture
- Multi-arch containers: amd64, arm64, arm/v7

### Requirements
- Python 3.11+
- For systemd: RPi.GPIO >= 0.7.0
- For Kubernetes: lgpio >= 0.2.2.0, Helm 3.x

## 📊 Test Coverage
- 98% overall code coverage
- 95% coverage for fan_control.py
- 99% coverage for temp_exporter.py

## 🙏 Contributors

**Michael Kuppinger (Mi-Q)**
- Email: michael@kuppinger.eu
- LinkedIn: [mkuppinger](https://www.linkedin.com/in/mkuppinger/)
- GitHub: [@Mi-Q](https://github.com/Mi-Q)

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Full Changelog**: https://github.com/Mi-Q/sipeed-cm5-fancontrol/blob/v0.2.0/CHANGELOG.md
