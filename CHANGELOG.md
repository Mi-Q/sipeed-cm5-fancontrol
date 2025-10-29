# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Kubernetes ConfigMap for fan controller configuration**
  - Fan controller settings managed via Kubernetes ConfigMap instead of file-based config
  - All configuration values customizable via Helm `values.yaml`
  - Easy updates with `helm upgrade --set` commands
  - GitOps-friendly configuration management
  - No need for `peers.conf` - Kubernetes auto-discovery handles peer management
- **Automatic GPIO library detection for deployment environments**
  - Kubernetes deployment: Uses `lgpio` library (works in containers on RPi 5/CM5)
  - Systemd deployment: Uses `RPi.GPIO` library (traditional approach)
  - Detects environment by checking for Kubernetes service account token
  - Seamless hardware GPIO access in both environments
  - Graceful fallback to DummyGPIO if libraries unavailable
- **Enhanced fan duty cycle logging**
  - Temperature logs now include current fan duty cycle percentage
  - Format: `Temperatures: local=40.2°C, http://10.42.4.18:8080/temp=34.8°C | Fan: 45.0%`
  - Provides complete visibility of fan controller operation
- **Automatic peer rediscovery in Kubernetes**
  - Fan controller rediscovers temperature exporter pods every ~1 minute
  - Handles pod restarts with new IP addresses gracefully
  - Logs "Peer list updated" when changes detected
  - No manual intervention needed when pods are rescheduled
- **CI/CD optimization for Docker image builds**
  - Images only build when relevant files change
  - Controller image: `fan_control.py`, `k8s_discovery.py`, `Dockerfile`
  - Exporter image: `temp_exporter.py`, `Dockerfile.exporter`
  - Faster CI runs for documentation-only changes
  - Reduced container registry API usage
- **Comprehensive Kubernetes documentation**
  - DaemonSets vs Deployments explanation
  - Five methods to stop/start/pause pods
  - Pod management guide with examples
  - Configuration customization examples
  - Hardware access requirements with lgpio details

### Changed
- **LGPIOWrapper and LGPIOPWMWrapper classes** provide RPi.GPIO-compatible interface for lgpio
- **Kubernetes Dockerfile** now installs lgpio with required dependencies (libgpiod-dev, swig)
- **requirements.txt** includes lgpio as conditional dependency for aarch64 platforms
- **Kubernetes README** updated with hardware access details and lgpio usage
- **Fan controller** periodic rediscovery enabled via `k8s_discovery_enabled` flag
- **Discovery interval** set to 12 polling cycles (~1 minute with 5s polls)

### Fixed
- **Reinstallation "Address already in use" errors completely resolved**
  - Added SO_REUSEADDR socket option to both `temp_exporter.py` and `fan_control.py`
  - Allows immediate port rebinding even when socket is in TIME_WAIT state
  - Installation script now uses `systemctl mask` to prevent automatic service restarts
  - Added `fuser -k` to forcefully kill zombie processes holding ports
  - Improved wait mechanism: 30-second timeout with per-second checks of service and port status
  - Script exits with detailed error if service doesn't stop or port isn't freed
  - Comprehensive cleanup process ensures reliable reinstallation
- **Installation script (install.sh) improvements**
  - Added detailed inline documentation explaining each step
  - Better error messages showing systemctl status and logs on failure
  - Three-phase stop process: mask → kill → stop for reliable service shutdown
  - Automatic detection and cleanup of failed systemd states
- **Simplified installation process**
  - Removed SSH polling option (HTTP-only for easier setup)
  - Eliminates need for SSH key configuration
  - One less manual step, better user experience

### Added
- **Real-time monitoring and status features**
  - HTTP status endpoint at `:8081/status` showing all temperatures and fan state
  - CLI tool `cm5fan` for querying fan controller status from command line
  - Enhanced logging showing individual node temperatures before aggregation
  - Status includes: mode, temperatures per node, aggregate temp, fan duty, configuration
- Comprehensive test suite with 94 unit tests achieving 98% code coverage
  - 95% coverage for fan_control.py
  - 99% coverage for temp_exporter.py
  - Tests for GPIO error handling, signal handlers, remote polling, and edge cases
- Configuration file support in `/etc/sipeed-cm5-fancontrol/` for fan control modes
  - **Manual mode**: Set fixed fan speed percentage (0-100%)
  - **Auto mode**: Automatic temperature-based control with configurable thresholds
  - Per-mode temperature and fan speed thresholds
- Interactive installation script (`install.sh`) with advanced features
  - One-line curl installation support
  - `--reinstall` flag to automatically upgrade existing installations
  - Detects existing installations and offers reinstall/reconfigure/cancel options
  - Safely stops services before reinstalling to prevent conflicts
  - Preserves existing configuration files during updates
  - Installs `fanctl` CLI tool to `/usr/local/bin/`
- Uninstallation script (`uninstall.sh`) with safe cleanup
  - Detects and stops all installed services
  - Optionally removes configuration files with user confirmation
  - Removes CLI tool
  - Cleans up installation directory
- Installation directory standardized to `/opt/sipeed-fancontrol`
  - Service files properly reference installation path
  - Dynamic path updates during installation for flexibility
- Temperature exporter service (`temp_exporter.py`) for HTTP-based temperature polling
  - Prometheus-compatible metrics endpoint at `:8080/metrics`
  - Plain text temperature endpoint at `:8080/temp`
- Remote temperature polling via HTTP and SSH methods
- Parallel peer temperature polling with ThreadPoolExecutor
- Support for aggregated temperature calculation (max, avg, min)
- Detailed documentation for Sipeed NanoCluster 7-slot architecture
- GitHub Actions CI/CD pipeline with testing, linting, and multi-arch container builds
- Pre-commit hooks with automatic black, isort, and flake8 checks
- Git hooks setup script (`setup-hooks.sh`) for easy developer onboarding
- CONTRIBUTING.md with development guidelines and testing instructions
- Flake8 configuration (`.flake8`) with 120 char line length (compatible with black)
- Comprehensive LICENSE (MIT) and versioning (VERSION file)

### Changed
- Renamed `systemd-sipeed-cm5-fancontrol/` to `deploy-systemd/` for better clarity
- Renamed `k3s-sipeed-cm5-fancontrol/` to `deploy-kubernetes/` for better clarity
- Updated all references in CI workflows, READMEs, Dockerfiles, and Helm charts
- Enhanced README with hardware platform details and k3s configuration requirements
- Improved code formatting consistency with black (88 char line length for code, 120 for max)
- Configured isort to be compatible with black formatting (profile="black")
- Changed GPIO import style to `import RPi.GPIO as GPIO` for improved clarity
- Updated service files to use `/opt/sipeed-fancontrol` as standard installation directory
- Temperature exporter port changed from 8000 to 8080 for consistency

### Fixed
- Python 3.14 compatibility issues in test suite
- Subprocess mocking to correctly use `check_output()` returning bytes
- Test assertions to match actual implementation behavior
- All flake8 linting errors (unused imports, formatting issues)
- Import ordering to follow isort standards
- Service file path inconsistencies resolved

## [0.1.0] - 2025-10-28

### Added
- Initial release of Sipeed CM5 Fan Control
- PWM-based fan control with configurable temperature thresholds
- Basic systemd service for fan control
- Kubernetes/Helm chart deployment support
- Multi-arch container images (amd64, arm64, arm/v7)
- Basic temperature reading from vcgencmd and sysfs
- Configurable min/max temperature and duty cycle parameters
- Dry-run mode for testing without GPIO hardware
- Basic logging and error handling

[Unreleased]: https://github.com/Mi-Q/sipeed-cm5-fancontrol/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Mi-Q/sipeed-cm5-fancontrol/releases/tag/v0.1.0
