#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

INSTALL_DIR="/opt/sipeed-fancontrol"
SERVICE_FILES=(
    "sipeed-cm5-fancontrol.service"
    "sipeed-temp-exporter.service"
)

echo "=================================================="
echo "  Sipeed NanoCluster Fan Control Uninstallation"
echo "=================================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Error: This script must be run as root (use sudo)${NC}"
    exit 1
fi

# Check which services are installed
INSTALLED_SERVICES=()
for service in "${SERVICE_FILES[@]}"; do
    if [ -f "/etc/systemd/system/$service" ]; then
        INSTALLED_SERVICES+=("$service")
    fi
done

if [ ${#INSTALLED_SERVICES[@]} -eq 0 ] && [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}No Sipeed fan control services found to uninstall.${NC}"
    exit 0
fi

echo "The following will be removed:"
echo ""
if [ ${#INSTALLED_SERVICES[@]} -gt 0 ]; then
    echo "Services:"
    for service in "${INSTALLED_SERVICES[@]}"; do
        SERVICE_NAME="${service%.service}"
        STATUS=$(systemctl is-active "$service" 2>/dev/null || echo "not-running")
        echo "  - $SERVICE_NAME (status: $STATUS)"
    done
    echo ""
fi
if [ -d "$INSTALL_DIR" ]; then
    echo "Installation directory:"
    echo "  - $INSTALL_DIR"
    echo ""
fi

read -p "Do you want to continue? [y/N]: " CONFIRM
case $CONFIRM in
    [yY]|[yY][eE][sS])
        ;;
    *)
        echo "Uninstallation cancelled."
        exit 0
        ;;
esac

echo ""
echo -e "${YELLOW}Uninstalling...${NC}"

# Stop and disable services
for service in "${INSTALLED_SERVICES[@]}"; do
    SERVICE_NAME="${service%.service}"
    echo "Stopping and disabling $SERVICE_NAME..."
    
    if systemctl is-active --quiet "$service"; then
        systemctl stop "$service" || echo -e "${YELLOW}Warning: Failed to stop $service${NC}"
    fi
    
    if systemctl is-enabled --quiet "$service" 2>/dev/null; then
        systemctl disable "$service" || echo -e "${YELLOW}Warning: Failed to disable $service${NC}"
    fi
    
    # Remove service file
    if [ -f "/etc/systemd/system/$service" ]; then
        rm -f "/etc/systemd/system/$service"
        echo -e "${GREEN}✓ Removed $service${NC}"
    fi
done

# Reload systemd
if [ ${#INSTALLED_SERVICES[@]} -gt 0 ]; then
    echo "Reloading systemd daemon..."
    systemctl daemon-reload
    systemctl reset-failed 2>/dev/null || true
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "Removing installation directory: $INSTALL_DIR"
    rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}✓ Removed $INSTALL_DIR${NC}"
fi

# Remove config file
if [ -f "/etc/sipeed-fancontrol.conf" ]; then
    read -p "Remove configuration file /etc/sipeed-fancontrol.conf? [y/N]: " REMOVE_CONFIG
    case $REMOVE_CONFIG in
        [yY]|[yY][eE][sS])
            rm -f "/etc/sipeed-fancontrol.conf"
            echo -e "${GREEN}✓ Removed /etc/sipeed-fancontrol.conf${NC}"
            ;;
        *)
            echo -e "${BLUE}Kept /etc/sipeed-fancontrol.conf${NC}"
            ;;
    esac
fi

# Remove cm5fan CLI tool
if [ -f "/usr/local/bin/cm5fan" ]; then
    rm -f "/usr/local/bin/cm5fan"
    echo -e "${GREEN}✓ Removed /usr/local/bin/cm5fan${NC}"
fi

echo ""
echo -e "${GREEN}✓ Uninstallation complete!${NC}"
echo ""
