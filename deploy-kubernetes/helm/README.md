# Sipeed CM5 Fan Controller

{{ template "chart.description" . }}

## TL;DR

```bash
cd deploy-kubernetes
./install.sh [namespace]
```

## Introduction

This chart deploys the Sipeed CM5 Fan Controller on a [Kubernetes](http://kubernetes.io) cluster using the [Helm](https://helm.sh) package manager.

## Prerequisites

- Kubernetes 1.16+
- Helm 3.0+
- PID access to GPIO (privileged container support)
- Access to temperature sensors on nodes

## Installing the Chart

To install the chart:

```bash
cd deploy-kubernetes
./install.sh [namespace]
```

The command deploys the fan controller on the Kubernetes cluster in the specified namespace. If no namespace is provided, it will use the `default` namespace.

## Uninstalling the Chart

To uninstall/delete the deployment:

```bash
helm uninstall sipeed-cm5-fancontrol -n [namespace]
```

## Configuration

The following table lists the configurable parameters of the chart and their default values.

### Controller Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `controller.image.repository` | Fan controller image repository | `ghcr.io/mi-q/sipeed-cm5-fancontrol` |
| `controller.image.tag` | Fan controller image tag | `latest` |
| `controller.image.pullPolicy` | Fan controller image pull policy | `Always` |
| `controller.resources.limits.cpu` | CPU limit | `100m` |
| `controller.resources.limits.memory` | Memory limit | `128Mi` |
| `controller.resources.requests.cpu` | CPU request | `50m` |
| `controller.resources.requests.memory` | Memory request | `64Mi` |
| `controller.args` | Fan controller arguments | See `values.yaml` |
| `controller.securityContext.privileged` | Run container as privileged (GPIO access) | `true` |
| `controller.service.port` | Status endpoint port | `2506` |

### Controller Configuration (ConfigMap)

| Parameter | Description | Default |
|-----------|-------------|---------|
| `controller.config.mode` | Fan control mode: `auto` or `manual` | `auto` |
| `controller.config.manualSpeed` | Manual mode fan speed (0-100) | `50` |
| `controller.config.tempLow` | Low temperature threshold (°C) | `30` |
| `controller.config.tempHigh` | High temperature threshold (°C) | `70` |
| `controller.config.fanSpeedLow` | Fan speed at tempLow (0-100) | `0` |
| `controller.config.fanSpeedHigh` | Fan speed at tempHigh (0-100) | `100` |
| `controller.config.fanMinOperatingSpeed` | Minimum fan speed to spin (0-100) | `10` |
| `controller.config.fanStopTemp` | Temperature below which fan stops (°C) | `20` |
| `controller.config.fanCurve` | Fan curve type: `linear`, `exponential`, or `step` | `exponential` |
| `controller.config.stepZones` | Step mode zones (temp:speed pairs) | `"35:0,45:30,55:60,65:100"` |
| `controller.config.stepHysteresis` | Step mode hysteresis (°C) | `2` |

### Exporter Settings

| Parameter | Description | Default |
|-----------|-------------|---------|
| `exporter.image.repository` | Temperature exporter image repository | `ghcr.io/mi-q/sipeed-temp-exporter` |
| `exporter.image.tag` | Temperature exporter image tag | `latest` |
| `exporter.image.pullPolicy` | Temperature exporter image pull policy | `Always` |
| `exporter.resources.limits.cpu` | CPU limit | `100m` |
| `exporter.resources.limits.memory` | Memory limit | `128Mi` |
| `exporter.resources.requests.cpu` | CPU request | `50m` |
| `exporter.resources.requests.memory` | Memory request | `64Mi` |
| `exporter.args` | Temperature exporter arguments | See `values.yaml` |
| `exporter.service.port` | Temperature exporter service port | `2505` |

### Examples

**Change temperature thresholds:**
```bash
helm upgrade sipeed-cm5-fancontrol ./helm \
  --set controller.config.tempLow=35 \
  --set controller.config.tempHigh=65
```

**Switch to manual mode:**
```bash
helm upgrade sipeed-cm5-fancontrol ./helm \
  --set controller.config.mode=manual \
  --set controller.config.manualSpeed=75
```

**Use step curve mode:**
```bash
helm upgrade sipeed-cm5-fancontrol ./helm \
  --set controller.config.fanCurve=step \
  --set controller.config.stepZones="30:0,40:40,50:70,60:100"
```

## Architecture

The chart deploys:
1. Fan Controller DaemonSet - Controls fan speed based on temperature
2. Temperature Exporter DaemonSet - Exposes temperature metrics
3. Temperature Exporter Service - Internal service for temperature polling

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.