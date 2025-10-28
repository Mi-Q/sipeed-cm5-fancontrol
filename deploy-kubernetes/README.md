# Sipeed CM5 Fan Control - Kubernetes Deployment

This directory contains the Kubernetes (k3s) deployment configuration using Helm charts for running the Sipeed CM5 Fan Controller in a cluster environment.

## Components

- `helm/` - Helm chart for deploying both the fan controller and temperature exporter
- `Dockerfile` - Fan controller container image
- `Dockerfile.exporter` - Temperature exporter container image
- `install.sh` - Helper script to install the Helm chart

## Prerequisites

- k3s/Kubernetes cluster running on Sipeed CM5 nodes
- Helm 3.x installed
- `kubectl` configured to access your cluster

## Installation

1. Install the Helm chart:
   ```bash
   ./install.sh [namespace]
   ```
   If namespace is not provided, it will use the `default` namespace.

2. Verify the installation:
   ```bash
   kubectl get pods -n [namespace]
   ```

## Configuration

The deployment can be customized through the `helm/values.yaml` file:

### Fan Controller Settings
- Image repository and tag
- Resource limits and requests
- Temperature polling configuration
- Security context

### Temperature Exporter Settings
- Image repository and tag
- Resource limits and requests
- Service configuration
- Port settings

## Architecture

The deployment consists of:
1. Fan Controller DaemonSet:
   - Runs on each node
   - Accesses GPIO for fan control
   - Polls temperatures from local and peer nodes

2. Temperature Exporter DaemonSet:
   - Exposes node temperature via HTTP
   - Prometheus-compatible metrics endpoint
   - Lightweight HTTP service

3. Temperature Exporter Service:
   - ClusterIP service for node discovery
   - Internal temperature API endpoint

## Security

The fan controller runs in privileged mode to access GPIO hardware. The temperature exporter requires read-only access to thermal information.

## Customization

To customize the deployment:

1. Edit `helm/values.yaml` with your settings
2. Upgrade the release:
   ```bash
   helm upgrade sipeed-cm5-fancontrol ./helm -n [namespace]
   ```

## Notes

- The fan controller needs privileged access to control GPIO
- The temperature exporter only needs read access to thermal data
- Both components use minimal resources and run as DaemonSets
- Multi-arch images support amd64, arm64, and arm/v7

## License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.