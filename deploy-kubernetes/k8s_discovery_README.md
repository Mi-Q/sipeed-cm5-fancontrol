# Kubernetes Discovery Module

This module provides automatic peer discovery for the fan controller when running in Kubernetes.

## Purpose

In Kubernetes deployments, worker nodes (and their temperature exporter pods) are dynamic:
- Nodes can be added/removed
- Pods have random names
- Pod IPs change on restart

This module uses the Kubernetes API to automatically discover all running temperature exporter pods, eliminating the need for manual peer configuration.

## Usage

This module is **only used in Kubernetes deployments** and is copied into the container image during build.

For **systemd deployments**, peer configuration is static and defined via command-line arguments:
```bash
--peers=node2,node3,node4 --remote-method=http
```

## How it Works

1. The fan controller starts with `--k8s-discovery` flag
2. Module checks if running inside Kubernetes pod
3. Uses in-cluster service account to query Kubernetes API
4. Lists all pods matching label selector `app.kubernetes.io/name=sipeed-temp-exporter`
5. Returns list of pod IPs with port 2505/temp endpoint
6. Fan controller polls all discovered pods

## Requirements

- Running inside Kubernetes pod
- ServiceAccount with `pods` list/get permissions (RBAC)
- `kubernetes` Python package installed in container
- `/var/run/secrets/kubernetes.io/serviceaccount/` mounted (automatic)

## Architecture

```
deploy-kubernetes/
  ├── k8s_discovery.py          # This module (K8s-specific)
  ├── Dockerfile                # Copies this module into container
  └── helm/templates/
      ├── controller-serviceaccount.yaml
      ├── controller-role.yaml
      └── controller-rolebinding.yaml

deploy-systemd/
  ├── fan_control.py            # Core logic (K8s-independent)
  └── (no k8s_discovery.py)     # Systemd doesn't need it
```

The core `fan_control.py` optionally imports this module when running in Kubernetes, maintaining full independence between deployment methods.
