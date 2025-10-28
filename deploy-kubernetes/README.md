# Sipeed CM5 Fan Control - Kubernetes Deployment

This directory contains the Kubernetes (k3s) deployment configuration using Helm charts for running the Sipeed CM5 Fan Controller in a cluster environment.

## Components

- `helm/` - Helm chart for deploying both the fan controller and temperature exporter
- `Dockerfile` - Fan controller container image
- `Dockerfile.exporter` - Temperature exporter container image
- `install.sh` - Helper script to install the Helm chart

## Features

### Fan Controller
- Automatic temperature-based fan speed control
- Multi-node temperature aggregation
- HTTP status endpoint at port 8081 for monitoring
- Real-time status including all node temperatures, aggregate temp, and fan duty cycle

### Temperature Exporter
- Exposes node temperature via HTTP on port 8080
- Prometheus-compatible metrics endpoint
- Lightweight HTTP service

## Prerequisites

- k3s/Kubernetes cluster running on Sipeed CM5 nodes
- Helm 3.x installed
- `kubectl` configured to access your cluster
- Master node labeled with `node-role.kubernetes.io/master=true`

### Node Labeling

Ensure your master node (Slot 1 with fan) is properly labeled:

```bash
# Check current labels
kubectl get nodes --show-labels

# Label the master node if needed
kubectl label nodes <master-node-name> node-role.kubernetes.io/master=true

# Verify the label
kubectl get nodes -l node-role.kubernetes.io/master=true
```

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

3. Test GPIO access (optional but recommended):
   ```bash
   # Check fan controller pod logs
   kubectl logs -n [namespace] -l app.kubernetes.io/name=sipeed-fan-controller
   
   # Verify GPIO is accessible
   kubectl exec -n [namespace] -it $(kubectl get pod -n [namespace] -l app.kubernetes.io/name=sipeed-fan-controller -o jsonpath='{.items[0].metadata.name}') -- ls -la /sys/class/gpio
   
   # Check if PWM is working (look for duty cycle changes in logs)
   kubectl logs -n [namespace] -l app.kubernetes.io/name=sipeed-fan-controller -f
   ```

4. Test temperature reading (optional but recommended):
   ```bash
   # Check temp exporter pod logs
   kubectl logs -n [namespace] -l app.kubernetes.io/name=sipeed-temp-exporter
   
   # Test temperature endpoint from within cluster
   kubectl run -it --rm debug --image=alpine --restart=Never -- wget -qO- http://sipeed-temp-exporter:8080/temp
   
   # Or port-forward and test locally
   kubectl port-forward -n [namespace] svc/sipeed-temp-exporter 8080:8080
   curl http://localhost:8080/temp
   ```

## Configuration

The deployment can be customized through the `helm/values.yaml` file:

### Fan Controller Settings
- Image repository and tag
- Resource limits and requests
- Temperature polling configuration
  - `--peers`: Comma-separated list of hostnames, IPs, or URLs (e.g., `node2,node3,192.168.1.104`)
  - `--remote-method`: Polling method (`http` or `ssh`)
  - Peers can be simple hostnames - full URLs are constructed automatically
- Security context

### Temperature Exporter Settings
- Image repository and tag
- Resource limits and requests
- Service configuration
- Port settings

### Example Peer Configuration

The `--peers` argument accepts flexible formats:
```yaml
# Simple hostnames (automatically expanded to http://hostname:8080/temp)
args:
  - --remote-method=http
  - --peers=node2,node3,node4

# Service names in Kubernetes
args:
  - --remote-method=http
  - --peers=sipeed-temp-exporter

# Full URLs (used as-is)
args:
  - --remote-method=http
  - --peers=http://node2:8080/temp,http://node3:8080/temp
```

## Architecture

The deployment consists of:
1. **Fan Controller DaemonSet** (Master Node Only):
   - Runs exclusively on the master node (node-role.kubernetes.io/master=true)
   - Accesses GPIO for fan control via `/sys` and `/dev` mounts
   - Runs with `privileged: true` and `hostPID: true` for hardware access
   - Polls temperatures from local and peer nodes
   - Provides HTTP status endpoint on port 8081
   - Only one instance per cluster

**Hardware Access Requirements:**
- The fan controller pod runs in privileged mode to access GPIO
- Host `/sys` and `/dev` directories are mounted into the container
- `hostPID: true` ensures proper hardware device access
- These settings allow the pod to control the PWM fan just like running on bare metal

2. **Temperature Exporter DaemonSet** (Worker Nodes Only):
   - Runs on all worker nodes (excludes master node)
   - Exposes node temperature via HTTP on port 8080
   - Reads temperature via `vcgencmd` (if available) or falls back to sysfs
   - Mounts `/sys/class/thermal` for sysfs temperature reading
   - Mounts `/dev/vcio` and `/dev/vchiq` for VideoCore GPU access (vcgencmd)
   - Prometheus-compatible metrics endpoint
   - Lightweight HTTP service
   - One instance per worker node

**Temperature Reading Methods:**
- Primary: `vcgencmd measure_temp` (requires VideoCore device access)
- Fallback: `/sys/class/thermal/thermal_zone0/temp` (always available)
- Both methods work in containers with proper device mounts

3. Services:
   - Temperature Exporter Service (port 8080): Internal temperature API endpoint
   - Fan Controller Service (port 8081): Status and monitoring endpoint

**Node Distribution:**
- Master node (Slot 1): Fan controller with GPIO access
- Worker nodes (Slots 2-7): Temperature exporters only
- Anti-affinity ensures no scheduling conflicts

## Monitoring

The fan controller exposes a status endpoint that provides real-time information:

```bash
# Query status from within the cluster
curl http://sipeed-fan-controller:8081/status
```

Response includes:
- Current fan control mode (manual/auto)
- Individual node temperatures
- Aggregate temperature
- Current fan duty cycle
- Controller configuration

You can also query a specific controller pod:
```bash
kubectl port-forward -n [namespace] pod/sipeed-fan-controller-xxxxx 8081:8081
curl http://localhost:8081/status
```

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