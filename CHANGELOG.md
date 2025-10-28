# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Comprehensive test suite with 94 unit tests achieving 98% code coverage
  - 95% coverage for fan_control.py
  - 99% coverage for temp_exporter.py
  - Tests for GPIO error handling, signal handlers, remote polling, and edge cases
- Interactive installation script (`install.sh`) with one-line curl installation support
- Temperature exporter service (`temp_exporter.py`) for HTTP-based temperature polling
- Remote temperature polling via HTTP and SSH methods
- Parallel peer temperature polling with ThreadPoolExecutor
- Prometheus-compatible metrics endpoint at `/metrics`
- Plain text temperature endpoint at `/temp`
- Support for aggregated temperature calculation (max, avg, min)
- Detailed documentation for Sipeed NanoCluster 7-slot architecture
- GitHub Actions CI/CD pipeline with testing, linting, and multi-arch container builds
- Pre-commit hooks with automatic black, isort, and flake8 checks
- Git hooks setup script (`setup-hooks.sh`) for easy developer onboarding
- CONTRIBUTING.md with development guidelines and testing instructions
- Flake8 configuration (`.flake8`) compatible with black (120 char line length)
- Comprehensive LICENSE (MIT) and versioning (VERSION file)

### Changed
- Renamed `systemd-sipeed-cm5-fancontrol/` to `deploy-systemd/` for better clarity
- Renamed `k3s-sipeed-cm5-fancontrol/` to `deploy-kubernetes/` for better clarity
- Updated all references in CI workflows, READMEs, Dockerfiles, and Helm charts
- Enhanced README with hardware platform details and k3s configuration requirements
- Improved code formatting consistency with black (88 char line length)
- Configured isort to be compatible with black formatting

### Fixed
- Python 3.14 compatibility issues in test suite
- Subprocess mocking to correctly use `check_output()` returning bytes
- Test assertions to match actual implementation behavior
- All flake8 linting errors (unused imports, formatting issues)
- Import ordering to follow isort standards

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
