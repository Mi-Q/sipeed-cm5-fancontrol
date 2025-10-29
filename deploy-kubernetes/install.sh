#!/usr/bin/env bash

# Script to install the Helm chart in k3s
set -euo pipefail

# Default namespace is default, but can be overridden
NAMESPACE=${1:-default}

echo "Installing Sipeed CM5 Fan Controller Helm chart in namespace ${NAMESPACE}..."

# Make sure helm is installed
if ! command -v helm &> /dev/null; then
    echo "Error: helm is not installed"
    exit 1
fi

# Add local chart
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
CHART_DIR="${SCRIPT_DIR}/helm"

# Install/upgrade the chart
helm upgrade --install sipeed-cm5-fancontrol "${CHART_DIR}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --wait

echo "Helm chart installed successfully!"
echo "Use 'kubectl -n ${NAMESPACE} get pods' to check the status"