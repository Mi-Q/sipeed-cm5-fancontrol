#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# GitHub repository details
GITHUB_REPO="Mi-Q/sipeed-cm5-fancontrol"
GITHUB_BRANCH="${INSTALL_BRANCH:-main}"
GITHUB_RAW_URL="https://raw.githubusercontent.com/${GITHUB_REPO}/${GITHUB_BRANCH}/deploy-systemd"

echo "=================================================="
echo "  Sipeed NanoCluster Fan Control Installation"
echo "=================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Detect if script is being piped from curl
if [ ! -t 0 ]; then
    PIPED_INSTALL=true
    echo -e "${BLUE}Detected remote installation mode${NC}"
else
    PIPED_INSTALL=false
fi

# Get the directory where the script is located
if [ "$PIPED_INSTALL" = true ]; then
    SCRIPT_DIR="/tmp/sipeed-fancontrol-install-$$"
    mkdir -p "$SCRIPT_DIR"
    echo "Downloading files from GitHub..."
    
    # Download required files
    for file in fan_control.py temp_exporter.py sipeed-cm5-fancontrol.service sipeed-temp-exporter.service; do
        echo "  - Downloading $file..."
        curl -sSL "${GITHUB_RAW_URL}/${file}" -o "${SCRIPT_DIR}/${file}" || {
            echo -e "${RED}Failed to download $file${NC}"
            exit 1
        }
    done
    echo -e "${GREEN}✓ Files downloaded successfully${NC}"
    echo ""
else
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
fi

echo "This script will install the appropriate service for your node."
echo ""
echo "Node Types:"
echo "  1) Fan Control Node - Controls the fan based on all node temperatures"
echo "     (Install on the node in Slot 1 with the fan header)"
echo ""
echo "  2) Temperature Provider Node - Exposes temperature via HTTP"
echo "     (Install on nodes in other slots)"
echo ""

# Prompt for node type
while true; do
    read -p "Which type of node is this? [1/2]: " NODE_TYPE
    case $NODE_TYPE in
        1)
            SERVICE_TYPE="fan-control"
            SERVICE_FILE="sipeed-cm5-fancontrol.service"
            SERVICE_NAME="sipeed-cm5-fancontrol"
            SCRIPT_FILE="fan_control.py"
            break
            ;;
        2)
            SERVICE_TYPE="temp-exporter"
            SERVICE_FILE="sipeed-temp-exporter.service"
            SERVICE_NAME="sipeed-temp-exporter"
            SCRIPT_FILE="temp_exporter.py"
            break
            ;;
        *)
            echo -e "${RED}Invalid option. Please enter 1 or 2.${NC}"
            ;;
    esac
done

echo ""
echo -e "${YELLOW}Installing ${SERVICE_TYPE} service...${NC}"

# Additional configuration for fan control node
if [ "$NODE_TYPE" = "1" ]; then
    echo ""
    echo "Enter the hostnames or IPs of peer nodes (comma-separated):"
    echo "Examples:"
    echo "  - Hostnames: node2,node3,node4,node5,node6,node7"
    echo "  - IPs: 192.168.1.102,192.168.1.103,192.168.1.104,..."
    echo "  - Mixed: node2,192.168.1.103,node4,node5,node6,node7"
    read -p "Peer nodes: " PEER_NODES
    
    echo ""
    echo "Select remote temperature polling method:"
    echo "  1) HTTP (recommended - uses temp_exporter.py on peer nodes)"
    echo "  2) SSH (requires SSH keys configured)"
    read -p "Method [1/2]: " REMOTE_METHOD
    
    case $REMOTE_METHOD in
        1)
            REMOTE_METHOD_ARG="http"
            ;;
        2)
            REMOTE_METHOD_ARG="ssh"
            ;;
        *)
            echo -e "${YELLOW}Invalid option, defaulting to HTTP${NC}"
            REMOTE_METHOD_ARG="http"
            ;;
    esac
fi

# Create installation directory
INSTALL_DIR="/opt/sipeed-fancontrol"
echo ""
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy Python script
echo "Copying $SCRIPT_FILE..."
cp "$SCRIPT_DIR/$SCRIPT_FILE" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/$SCRIPT_FILE"

# Copy service file and modify if needed
echo "Installing systemd service..."
if [ "$NODE_TYPE" = "1" ] && [ -n "$PEER_NODES" ]; then
    # Modify service file with peer configuration
    sed "s|ExecStart=.*|ExecStart=/usr/bin/python3 $INSTALL_DIR/$SCRIPT_FILE --peers $PEER_NODES --remote-method $REMOTE_METHOD_ARG|g" \
        "$SCRIPT_DIR/$SERVICE_FILE" > "/etc/systemd/system/$SERVICE_NAME.service"
else
    cp "$SCRIPT_DIR/$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
fi

# Update WorkingDirectory in service file
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" "/etc/systemd/system/$SERVICE_NAME.service"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start service
echo "Enabling and starting $SERVICE_NAME service..."
systemctl enable "$SERVICE_NAME.service"
systemctl start "$SERVICE_NAME.service"

# Check service status
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
    echo ""
    echo -e "${GREEN}✓ Installation successful!${NC}"
    echo ""
    echo "Service: $SERVICE_NAME"
    echo "Status: $(systemctl is-active $SERVICE_NAME.service)"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    sudo journalctl -u $SERVICE_NAME.service -f"
    echo "  Stop service: sudo systemctl stop $SERVICE_NAME.service"
    echo "  Restart:      sudo systemctl restart $SERVICE_NAME.service"
    echo "  Disable:      sudo systemctl disable $SERVICE_NAME.service"
    
    if [ "$NODE_TYPE" = "2" ]; then
        echo ""
    echo -e "${GREEN}Temperature endpoint available at: http://$(hostname -I | awk '{print $1}'):8080/temp${NC}"
    echo -e "${GREEN}Metrics endpoint available at: http://$(hostname -I | awk '{print $1}'):8080/metrics${NC}"
    fi
else
    echo ""
    echo -e "${RED}✗ Service failed to start${NC}"
    echo "Check logs with: sudo journalctl -u $SERVICE_NAME.service -n 50"
    exit 1
fi

# Cleanup temporary directory if this was a piped install
if [ "$PIPED_INSTALL" = true ]; then
    echo ""
    echo "Cleaning up temporary files..."
    rm -rf "$SCRIPT_DIR"
fi

echo ""
echo "=================================================="
