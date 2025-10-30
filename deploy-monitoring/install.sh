#!/bin/bash
set -e

# Sipeed CM5 Monitoring Stack Installation Script
# Deploys Prometheus + Grafana for monitoring temperature and fan speed

NAMESPACE="${1:-sipeed-cm5-fancontrol}"

echo "========================================="
echo "Sipeed CM5 Monitoring Stack Installation"
echo "========================================="
echo ""
echo "Installing monitoring stack in namespace: $NAMESPACE"
echo ""

# Check if fan control is installed
echo "Checking if fan control is deployed..."
if ! kubectl get namespace "$NAMESPACE" &> /dev/null; then
    echo "ERROR: Namespace '$NAMESPACE' does not exist!"
    echo "Please install the fan control system first:"
    echo "  cd ../deploy-kubernetes && ./install.sh $NAMESPACE"
    exit 1
fi

if ! kubectl get deployment sipeed-fan-controller -n "$NAMESPACE" &> /dev/null && \
   ! kubectl get daemonset sipeed-fan-controller -n "$NAMESPACE" &> /dev/null; then
    echo "WARNING: Fan controller not found in namespace '$NAMESPACE'"
    echo "Make sure the fan control system is installed first."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✓ Fan control system detected"
echo ""

# Install Helm chart
echo "Installing Helm chart..."
helm upgrade --install sipeed-monitoring ./helm \
    --namespace "$NAMESPACE" \
    --create-namespace \
    --wait

echo ""
echo "========================================="
echo "Installation Complete!"
echo "========================================="
echo ""
echo "📊 Access Grafana:"
echo ""
echo "  1. Get any node IP:"
echo "     kubectl get nodes -o wide"
echo ""
echo "  2. Access Grafana at:"
echo "     http://<NODE-IP>:30300"
echo ""
echo "  3. Login credentials:"
echo "     Username: admin"
echo "     Password: admin123"
echo ""
echo "  ⚠️  IMPORTANT: Change the default password after first login!"
echo ""
echo "🔍 The dashboard 'Sipeed CM5 - Temperature & Fan Control' is pre-installed"
echo ""
echo "📈 Prometheus UI (optional):"
echo "   kubectl port-forward -n $NAMESPACE svc/sipeed-prometheus 9090:9090"
echo "   Then access: http://localhost:9090"
echo ""
echo "🔧 Useful commands:"
echo "   - Check pods:    kubectl get pods -n $NAMESPACE"
echo "   - Grafana logs:  kubectl logs -n $NAMESPACE -l app=grafana -f"
echo "   - Prometheus logs: kubectl logs -n $NAMESPACE -l app=prometheus -f"
echo ""
