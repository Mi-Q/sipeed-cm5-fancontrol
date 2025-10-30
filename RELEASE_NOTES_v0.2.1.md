# Release Notes - v0.2.1

**Release Date:** January 13, 2025  
**Release Type:** Patch Release

## Summary

Version 0.2.1 updates the default TCP ports used by the Sipeed CM5 Fan Control system to avoid conflicts with other common services.

## Port Changes

| Service | Old Port | New Port |
|---------|----------|----------|
| Temperature Exporter | 8080 | 2505 |
| Status Endpoint | 8081 | 2506 |

## What Changed

### Core Components
- ✅ `fan_control.py`: Updated status port default (2506) and temperature polling URL format
- ✅ `temp_exporter.py`: Updated default port (2505)
- ✅ `k8s_discovery.py`: Updated Kubernetes discovery port (2505)

### Systemd Deployment
- ✅ `sipeed-cm5-fancontrol.service`: Updated status port argument
- ✅ `sipeed-temp-exporter.service`: Updated port argument
- ✅ `README.md`: Updated all examples and documentation

### Kubernetes Deployment
- ✅ `helm/values.yaml`: Updated service ports
- ✅ `helm/Chart.yaml`: Version bump to 0.2.1
- ✅ `helm/templates/controller-daemonset.yaml`: Updated container port
- ✅ `helm/tests/test-values.yaml`: Updated test assertions
- ✅ `README.md`: Updated all examples and documentation
- ✅ `helm/README.md`: Updated configuration tables

### Documentation
- ✅ Root `README.md`: Updated port references
- ✅ `CHANGELOG.md`: Added v0.2.1 entry
- ✅ `k8s_discovery_README.md`: Updated port reference

### Tests
- ✅ All unit tests updated to use new ports (2505)
- ✅ Test assertions updated

### Version Files
- ✅ `VERSION`: Updated to 0.2.1
- ✅ `deploy-kubernetes/helm/Chart.yaml`: Version and appVersion updated

## Upgrade Instructions

### Systemd Deployment

For existing installations, you can either:

**Option 1: Reinstall (Recommended)**
```bash
cd deploy-systemd
sudo ./uninstall.sh
sudo ./install.sh
```

**Option 2: Manual Update**
```bash
# Stop services
sudo systemctl stop sipeed-cm5-fancontrol.service
sudo systemctl stop sipeed-temp-exporter.service

# Pull latest changes
git pull origin main
git checkout v0.2.1

# Copy updated service files
sudo cp deploy-systemd/sipeed-cm5-fancontrol.service /etc/systemd/system/
sudo cp deploy-systemd/sipeed-temp-exporter.service /etc/systemd/system/

# Reload systemd and restart services
sudo systemctl daemon-reload
sudo systemctl start sipeed-cm5-fancontrol.service
sudo systemctl start sipeed-temp-exporter.service
```

**Important:** If you have firewall rules restricting ports, update them:
- Allow incoming on port 2505 (temperature exporter)
- Allow outgoing to port 2505 (for polling peers)
- Status endpoint on 2506 (if accessed remotely)

### Kubernetes Deployment

Update your Helm deployment:

```bash
# Pull latest changes
cd deploy-kubernetes
git pull origin main
git checkout v0.2.1

# Upgrade the Helm release
helm upgrade sipeed-cm5-fancontrol ./helm -n sipeed-cm5-fancontrol
```

The upgrade will:
- Update service ports (ClusterIP addresses remain unchanged)
- Restart controller and exporter pods with new ports
- Automatically reconnect after pod restarts (using auto-discovery)

**Verify the upgrade:**
```bash
# Check pods are running
kubectl get pods -n sipeed-cm5-fancontrol

# Test new port
kubectl run -it --rm debug --image=alpine --restart=Never -- wget -qO- http://sipeed-temp-exporter:2505/temp

# Check status endpoint
kubectl port-forward -n sipeed-cm5-fancontrol svc/sipeed-fan-controller 2506:2506
curl http://localhost:2506/status
```

## Breaking Changes

⚠️ **Port change is a breaking change if:**
- You have firewall rules explicitly allowing ports 8080/8081
- You have monitoring tools configured to scrape port 8080
- You have custom scripts accessing these ports
- You're mixing v0.2.0 and v0.2.1 nodes in the same cluster

**Solution:** Update all nodes to v0.2.1 simultaneously to maintain compatibility.

## Compatibility

- ✅ Compatible with existing fan control configurations
- ✅ No changes to fan control logic or behavior
- ✅ ConfigMap settings remain unchanged
- ⚠️ Not compatible with v0.2.0 nodes (different ports)

## Testing

All changes have been validated:
- ✅ Unit tests updated and passing
- ✅ Systemd service files tested
- ✅ Kubernetes deployment tested
- ✅ No old port references in production code

## Links

- **Release:** https://github.com/Mi-Q/sipeed-cm5-fancontrol/releases/tag/v0.2.1
- **Full Changelog:** https://github.com/Mi-Q/sipeed-cm5-fancontrol/compare/v0.2.0...v0.2.1
- **Commit:** 9ddbd3f

## Credits

Thank you for using Sipeed CM5 Fan Control! 

For issues or questions, please visit: https://github.com/Mi-Q/sipeed-cm5-fancontrol/issues
