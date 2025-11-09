#!/bin/bash
# Full deployment script for Sipeed CM5 monitoring system with enhanced metrics

set -e

KUBECONFIG_PATH="/Users/kuppinger/Library/Application Support/Lens/kubeconfigs/8e9d609f-bb65-4145-ae88-23e09ecd9606-pasted-kubeconfig.yaml"
export KUBECONFIG="$KUBECONFIG_PATH"

echo "======================================"
echo "Sipeed CM5 Full Deployment"
echo "======================================"
echo ""

# Wait for CI to complete
echo "→ Checking CI pipeline status..."
while true; do
    gh run list --limit 1 --json status,conclusion > /tmp/gh_status.json
    status=$(cat /tmp/gh_status.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0]['status'] if data else 'unknown')")
    conclusion=$(cat /tmp/gh_status.json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data[0].get('conclusion', 'none') if data else 'none')")
    
    if [ "$status" = "completed" ]; then
        if [ "$conclusion" = "success" ]; then
            echo "✓ CI pipeline completed successfully"
            break
        else
            echo "✗ CI pipeline failed with conclusion: $conclusion"
            exit 1
        fi
    fi
    
    echo "  Waiting for CI to complete (status: $status)..."
    sleep 10
done

echo ""
echo "→ Creating namespace..."
kubectl create namespace sipeed-cm5-fancontrol --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "→ Deploying temperature exporters (on all 4 nodes)..."
helm upgrade --install sipeed-monitoring ./deploy-kubernetes/helm \
    -n sipeed-cm5-fancontrol \
    --wait \
    --timeout=5m

echo ""
echo "→ Deploying monitoring stack (Grafana + Prometheus)..."
helm upgrade --install sipeed-monitoring-stack ./deploy-monitoring/helm \
    -n sipeed-cm5-fancontrol \
    --wait \
    --timeout=5m

echo ""
echo "→ Waiting for all pods to be ready..."
kubectl wait --for=condition=ready pod --all -n sipeed-cm5-fancontrol --timeout=300s

echo ""
echo "======================================"
echo "✓ Deployment Complete!"
echo "======================================"
echo ""
echo "📊 Check status:"
echo "  kubectl get pods -n sipeed-cm5-fancontrol -o wide"
echo ""
echo "🌐 Access Grafana:"
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
echo "  http://$NODE_IP:30300"
echo "  Username: admin"
echo "  Password: admin123"
echo ""
echo "📈 Check metrics:"
echo "  curl http://$NODE_IP:30500/metrics"
echo ""
echo "🔍 View logs:"
echo "  kubectl logs -n sipeed-cm5-fancontrol -l app.kubernetes.io/name=sipeed-temp-exporter --tail=20"
echo ""
