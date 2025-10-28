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

| Parameter | Description | Default |
|-----------|-------------|---------|
| `controller.image.repository` | Fan controller image repository | `ghcr.io/mi-q/sipeed-cm5-fancontrol` |
| `controller.image.tag` | Fan controller image tag | `latest` |
| `controller.image.pullPolicy` | Fan controller image pull policy | `IfNotPresent` |
| `controller.resources` | Fan controller pod resource requests & limits | `{}` |
| `controller.args` | Fan controller arguments | `[]` |
| `controller.securityContext.privileged` | Run controller container as privileged | `true` |
| `exporter.image.repository` | Temperature exporter image repository | `ghcr.io/mi-q/sipeed-temp-exporter` |
| `exporter.image.tag` | Temperature exporter image tag | `latest` |
| `exporter.image.pullPolicy` | Temperature exporter image pull policy | `IfNotPresent` |
| `exporter.resources` | Temperature exporter pod resource requests & limits | `{}` |
| `exporter.args` | Temperature exporter arguments | `[]` |
| `exporter.service.port` | Temperature exporter service port | `8080` |

## Architecture

The chart deploys:
1. Fan Controller DaemonSet - Controls fan speed based on temperature
2. Temperature Exporter DaemonSet - Exposes temperature metrics
3. Temperature Exporter Service - Internal service for temperature polling

## License

This project is licensed under the MIT License - see the [LICENSE](../../LICENSE) file for details.