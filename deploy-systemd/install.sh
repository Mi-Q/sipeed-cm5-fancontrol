#!/bin/bash
#
# Sipeed NanoCluster Fan Control Installation Script
# 
# This script installs and configures fan control services for the Sipeed NanoCluster.
# It supports two types of nodes:
#   1. Fan Control Node - Controls the fan based on temperatures from all nodes
#   2. Temperature Provider Node - Exposes temperature readings via HTTP
#
# Usage:
#   sudo ./install.sh              # Interactive installation
#   sudo ./install.sh --reinstall  # Automatic reinstall/update
#   sudo ./install.sh --help       # Show help
#
# Remote installation:
#   curl -sSL <url>/install.sh | sudo bash
#
# Features:
#   - Detects existing installations and offers reinstall/reconfigure options
#   - Properly stops services and waits for ports to be released during reinstall
#   - Uses systemctl mask to prevent automatic restarts during reinstallation
#   - Forcefully kills zombie processes that don't release ports
#   - Validates service starts successfully before completing
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse command line arguments
AUTO_REINSTALL=false
for arg in "$@"; do
    case $arg in
        --reinstall|-r)
            AUTO_REINSTALL=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --reinstall, -r    Automatically reinstall if installation exists"
            echo "  --help, -h         Show this help message"
            exit 0
            ;;
    esac
done

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
    for file in fan_control.py temp_exporter.py sipeed-cm5-fancontrol.service sipeed-temp-exporter.service fan_control.conf cli/cm5fan; do
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

# Check for existing installation
INSTALL_DIR="/opt/sipeed-fancontrol"
EXISTING_SERVICES=()
if [ -f "/etc/systemd/system/sipeed-cm5-fancontrol.service" ]; then
    EXISTING_SERVICES+=("sipeed-cm5-fancontrol")
fi
if [ -f "/etc/systemd/system/sipeed-temp-exporter.service" ]; then
    EXISTING_SERVICES+=("sipeed-temp-exporter")
fi

if [ ${#EXISTING_SERVICES[@]} -gt 0 ] || [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Existing installation detected:${NC}"
    echo ""
    if [ ${#EXISTING_SERVICES[@]} -gt 0 ]; then
        echo "Installed services:"
        for service in "${EXISTING_SERVICES[@]}"; do
            STATUS=$(systemctl is-active "$service.service" 2>/dev/null || echo "inactive")
            echo "  - $service (status: $STATUS)"
        done
        echo ""
    fi
    if [ -d "$INSTALL_DIR" ]; then
        echo "Installation directory: $INSTALL_DIR"
        echo ""
    fi
    
    if [ "$AUTO_REINSTALL" = true ]; then
        INSTALL_OPTION=1
        echo -e "${YELLOW}Auto-reinstall requested, proceeding...${NC}"
    else
        echo "Options:"
        echo "  1) Reinstall/Update - Replace existing installation"
        echo "  2) Reconfigure - Update service configuration only"
        echo "  3) Cancel - Exit without changes"
        echo ""
        read -p "Choose option [1/2/3]: " INSTALL_OPTION
    fi
    
    case $INSTALL_OPTION in
        1)
            echo ""
            echo -e "${YELLOW}Proceeding with reinstall...${NC}"
            
            # Stop existing services and ensure clean state before reinstalling
            # This prevents "Address already in use" errors during reinstallation
            for service in "${EXISTING_SERVICES[@]}"; do
                echo "Stopping $service..."
                
                # Step 1: Mask service to prevent any automatic restart attempts by systemd
                systemctl mask "$service.service" 2>/dev/null || true
                
                # Step 2: Forcefully kill any running processes
                systemctl kill "$service.service" 2>/dev/null || true
                
                # Step 3: Stop the service cleanly
                systemctl stop "$service.service" 2>/dev/null || true
                
                # Determine which port this service uses
                if [ "$service" = "sipeed-cm5-fancontrol" ]; then
                    PORT_TO_CHECK=8081  # Fan control status endpoint
                elif [ "$service" = "sipeed-temp-exporter" ]; then
                    PORT_TO_CHECK=8080  # Temperature exporter endpoint
                else
                    continue
                fi
                
                # Wait for service to become inactive and port to be released
                echo "Waiting for $service to stop completely and port $PORT_TO_CHECK to be released..."
                TIMEOUT=30
                ELAPSED=0
                SERVICE_INACTIVE=false
                PORT_FREE=false
                
                while (( ELAPSED < TIMEOUT )); do
                    # Check if service is inactive
                    if ! systemctl is-active --quiet "$service.service"; then
                        SERVICE_INACTIVE=true
                    fi
                    
                    # Check if port is free
                    if ! ss -tlnH "sport = :$PORT_TO_CHECK" 2>/dev/null | grep -q ":$PORT_TO_CHECK"; then
                        PORT_FREE=true
                    fi
                    
                    # Success - both conditions met
                    if [ "$SERVICE_INACTIVE" = true ] && [ "$PORT_FREE" = true ]; then
                        echo "✓ $service stopped and port $PORT_TO_CHECK released (after ${ELAPSED}s)"
                        break
                    fi
                    
                    # Handle zombie processes: if service is inactive but port still bound,
                    # forcefully kill the process holding the port after 5 seconds
                    if [ "$SERVICE_INACTIVE" = true ] && [ "$PORT_FREE" != true ] && [ "$ELAPSED" -gt 5 ]; then
                        echo "Service inactive but port still in use, force-killing process..."
                        fuser -k ${PORT_TO_CHECK}/tcp 2>/dev/null || true
                    fi
                    
                    sleep 1
                    ELAPSED=$((ELAPSED + 1))
                done
                
                # Report errors if timeout reached
                if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
                    if [ "$SERVICE_INACTIVE" != true ]; then
                        echo -e "${RED}Error: Service $service still active after ${TIMEOUT}s${NC}"
                        systemctl status "$service.service" --no-pager || true
                        exit 1
                    fi
                    if [ "$PORT_FREE" != true ]; then
                        echo -e "${RED}Error: Port $PORT_TO_CHECK still in use after ${TIMEOUT}s${NC}"
                        echo "Port usage:"
                        ss -tlnp | grep ":$PORT_TO_CHECK" || true
                        exit 1
                    fi
                fi
                
                # Clean up systemd state for fresh installation
                systemctl reset-failed "$service.service" 2>/dev/null || true
                systemctl unmask "$service.service" 2>/dev/null || true
            done
            echo ""
            ;;
        2)
            RECONFIGURE_ONLY=true
            echo ""
            echo -e "${YELLOW}Reconfiguring existing installation...${NC}"
            echo ""
            ;;
        3|*)
            echo "Installation cancelled."
            exit 0
            ;;
    esac
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
    
    # Always use HTTP method (SSH removed for simplicity)
    REMOTE_METHOD_ARG="http"
    echo ""
    echo -e "${BLUE}Using HTTP polling method (port 8080 on peer nodes)${NC}"
fi

# Create installation directory
echo ""
echo "Creating installation directory: $INSTALL_DIR"
mkdir -p "$INSTALL_DIR"

# Copy Python script (skip if reconfigure only)
if [ "$RECONFIGURE_ONLY" != true ]; then
    echo "Copying $SCRIPT_FILE..."
    cp "$SCRIPT_DIR/$SCRIPT_FILE" "$INSTALL_DIR/"
    chmod +x "$INSTALL_DIR/$SCRIPT_FILE"
    
    # Copy CLI tool for fan control node
    if [ "$NODE_TYPE" = "1" ]; then
        echo "Installing cm5fan CLI tool..."
        cp "$SCRIPT_DIR/cli/cm5fan" "/usr/local/bin/cm5fan"
        chmod +x "/usr/local/bin/cm5fan"
    fi
    
    # Copy config file for fan control node (only if it doesn't exist)
    if [ "$NODE_TYPE" = "1" ]; then
        if [ ! -f "/etc/sipeed-fancontrol.conf" ]; then
            echo "Installing configuration file..."
            cp "$SCRIPT_DIR/fan_control.conf" "/etc/sipeed-fancontrol.conf"
            echo -e "${GREEN}✓ Config file installed at /etc/sipeed-fancontrol.conf${NC}"
            echo -e "${BLUE}  Edit this file to switch between auto/manual mode${NC}"
        else
            echo "Config file already exists at /etc/sipeed-fancontrol.conf (keeping existing)"
        fi
    fi
else
    echo "Skipping file copy (reconfigure only)..."
fi

# Copy service file and modify if needed
echo "Installing systemd service..."
if [ "$NODE_TYPE" = "1" ] && [ -n "$PEER_NODES" ]; then
    # Modify service file with peer configuration
    sed "s|ExecStart=.*|ExecStart=/usr/bin/python3 $INSTALL_DIR/$SCRIPT_FILE --peers $PEER_NODES --remote-method $REMOTE_METHOD_ARG|g" \
        "$SCRIPT_DIR/$SERVICE_FILE" > "/etc/systemd/system/$SERVICE_NAME.service"
else
    cp "$SCRIPT_DIR/$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
fi

# Update WorkingDirectory and ExecStart paths in service file
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" "/etc/systemd/system/$SERVICE_NAME.service"
sed -i "s|ExecStart=/usr/bin/python3 .*/\([^/]*\.py\)|ExecStart=/usr/bin/python3 $INSTALL_DIR/\1|g" "/etc/systemd/system/$SERVICE_NAME.service"

# Reload systemd
echo "Reloading systemd daemon..."
systemctl daemon-reload

# Stop service if running (ensures port is freed before restart)
if systemctl is-active --quiet "$SERVICE_NAME.service"; then
    echo "Stopping existing $SERVICE_NAME service..."
    systemctl stop "$SERVICE_NAME.service"
    
    # Determine which port to check based on service type
    if [ "$SERVICE_NAME" = "sipeed-cm5-fancontrol" ]; then
        PORT_TO_CHECK=8081
    elif [ "$SERVICE_NAME" = "sipeed-temp-exporter" ]; then
        PORT_TO_CHECK=8080
    else
        echo -e "${RED}Error: Unknown service name '$SERVICE_NAME'. Cannot determine port to check.${NC}"
        exit 1
    fi
    
    # Wait for service to become inactive and port to be released
    echo "Waiting for service to stop and port $PORT_TO_CHECK to be released..."
    TIMEOUT=30
    ELAPSED=0
    SERVICE_INACTIVE=false
    PORT_FREE=false
    
    while (( ELAPSED < TIMEOUT )); do
        # Check if service is inactive
        if ! systemctl is-active --quiet "$SERVICE_NAME.service"; then
            SERVICE_INACTIVE=true
        fi
        
        # Check if port is free
        if ! ss -tlnH "sport = :$PORT_TO_CHECK" 2>/dev/null | grep -q ":$PORT_TO_CHECK"; then
            PORT_FREE=true
        fi
        
        # Exit loop if both conditions are met
        if [ "$SERVICE_INACTIVE" = true ] && [ "$PORT_FREE" = true ]; then
            echo "Service inactive and port $PORT_TO_CHECK is now available (after ${ELAPSED}s)"
            break
        fi
        
        sleep 1
        ELAPSED=$((ELAPSED + 1))
    done
    
    # Report timeout warnings
    if [ "$ELAPSED" -ge "$TIMEOUT" ]; then
        if [ "$SERVICE_INACTIVE" != true ]; then
            echo -e "${RED}Error: Service $SERVICE_NAME still active after ${TIMEOUT}s${NC}"
            exit 1
        fi
        if [ "$PORT_FREE" != true ]; then
            echo -e "${RED}Error: Port $PORT_TO_CHECK still in use after ${TIMEOUT}s${NC}"
            exit 1
        fi
    fi
fi

# Enable and start service
# Note: SO_REUSEADDR is enabled in both fan_control.py and temp_exporter.py
# to allow immediate port reuse, preventing "Address already in use" errors
echo "Enabling and starting $SERVICE_NAME service..."
systemctl enable "$SERVICE_NAME.service"

# Start the service and capture any immediate startup errors
if ! systemctl start "$SERVICE_NAME.service" 2>&1; then
    echo ""
    echo -e "${RED}✗ Failed to start service${NC}"
    echo ""
    echo "Service status:"
    systemctl status "$SERVICE_NAME.service" --no-pager -l || true
    echo ""
    echo "Recent logs:"
    journalctl -u "$SERVICE_NAME.service" -n 30 --no-pager
    exit 1
fi

# Verify service is running after a brief startup period
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
    echo -e "${RED}✗ Service failed to start or crashed immediately${NC}"
    echo ""
    echo "Service status:"
    systemctl status "$SERVICE_NAME.service" --no-pager -l || true
    echo ""
    echo "Recent logs:"
    journalctl -u "$SERVICE_NAME.service" -n 30 --no-pager
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
