# Sipeed CM5 Fan Control - Kubernetes Deployment

This directory contains the Kubernetes (k3s) deployment configuration using Helm charts for running the Sipeed CM5 Fan Controller in a cluster environment.

## Components

- `helm/` - Helm chart for deploying both the fan controller and temperature exporter
- `Dockerfile` - Fan controller container image
- `Dockerfile.exporter` - Temperature exporter container image
- `k8s_discovery.py` - Kubernetes-specific peer discovery module
- `install.sh` - Helper script to install the Helm chart

## Key Differences from Systemd Deployment

**Kubernetes deployment** uses dynamic peer discovery:
- No need to manually configure peer addresses
- Automatically discovers all temperature exporter pods via Kubernetes API
- Adapts to nodes being added/removed from cluster
- Uses RBAC and ServiceAccount for API access

**Systemd deployment** uses static peer configuration:
- Peers defined at installation time via `install.sh`
- Static list in systemd service file
- See `../deploy-systemd/README.md` for details

Both deployments share the same core `fan_control.py` logic, which gracefully handles both modes.

## Features

### Fan Controller
- Automatic temperature-based fan speed control
- **Kubernetes-native peer discovery** - Automatically discovers all temp exporter pods
- No manual peer configuration needed - dynamically adapts to cluster changes
- Multi-node temperature aggregation
- HTTP status endpoint at port 8081 for monitoring
- Real-time status including all node temperatures, aggregate temp, and fan duty cycle
- RBAC-based Kubernetes API access for pod discovery

### Temperature Exporter
- Exposes node temperature via HTTP on port 8080
- Prometheus-compatible metrics endpoint
- Lightweight HTTP service
- Runs on all worker nodes (excludes master)

## Prerequisites

- k3s/Kubernetes cluster running on Sipeed CM5 nodes
- Helm 3.x installed
- `kubectl` configured to access your cluster
- Control plane node labeled with `node-role.kubernetes.io/control-plane=true`

### Node Labeling

Ensure your control plane node (Slot 1 with fan) is properly labeled:

```bash
# Check current labels
kubectl get nodes --show-labels

# Label the control plane node if needed
kubectl label nodes <control-plane-node-name> node-role.kubernetes.io/control-plane=true

# Verify the label
kubectl get nodes -l node-role.kubernetes.io/control-plane=true
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

### Automatic Peer Discovery (Default)

The fan controller uses **Kubernetes API-based peer discovery** by default. No manual configuration needed!

**How it works:**
1. Fan controller pod uses a ServiceAccount with permissions to list pods
2. Queries Kubernetes API for pods matching label: `app.kubernetes.io/name=sipeed-temp-exporter`
3. Automatically discovers all running temp exporter pods in the namespace
4. Polls each discovered pod's IP address directly
5. Dynamically adapts when nodes are added/removed

**RBAC Resources:**
- `ServiceAccount`: `sipeed-fan-controller`
- `Role`: Grants `list` and `get` permissions for pods
- `RoleBinding`: Links ServiceAccount to Role

This is enabled by default with the `--k8s-discovery` flag in `values.yaml`:
```yaml
controller:
  args:
    - --remote-method=http
    - --k8s-discovery  # Auto-discovers all temp exporter pods
    - --status-port=8081
```

### Manual Peer Configuration (Optional)

You can override auto-discovery with static peers if needed:

```yaml
controller:
  args:
    - --remote-method=http
    - --peers=node2,node3,node4  # Static peer list
    - --status-port=8081
```

### Fan Controller Settings
- Image repository and tag
- Resource limits and requests
- Discovery method (auto or manual)
- Security context (privileged mode for GPIO access)

### Temperature Exporter Settings
- Image repository and tag
- Resource limits and requests
- Service configuration
- Port settings

## Architecture

The deployment consists of:
1. **Fan Controller DaemonSet** (Control Plane Node Only):
   - Runs exclusively on the control plane node (node-role.kubernetes.io/control-plane=true)
   - Accesses GPIO for fan control via `/sys` and `/dev` mounts
   - Runs with `privileged: true` and `hostPID: true` for hardware access
   - Polls temperatures from local and peer nodes
   - Provides HTTP status endpoint on port 8081
   - Only one instance per cluster

**Hardware Access Requirements:**
- The fan controller pod runs in privileged mode to access GPIO
- Uses **lgpio** library (modern GPIO library that works in containers on RPi 5/CM5)
- Automatically detects Kubernetes environment and uses lgpio instead of RPi.GPIO
- On systemd deployments, continues using RPi.GPIO (traditional approach)
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