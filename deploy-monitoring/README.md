# Sipeed CM5 Fan Control - Monitoring Stack

Grafana + Prometheus monitoring solution for visualizing CPU temperatures and fan speed across your Sipeed CM5 cluster.

## 📊 Features

- **Real-time temperature monitoring** for all cluster nodes
- **Fan speed tracking** with gauge and historical graph
- **Pre-configured Grafana dashboard** with 4 visualization panels:
  - CPU temperature time series (per node)
  - Current fan speed gauge
  - Fan speed history graph
  - Temperature bar chart for all nodes
- **Auto-refresh every 5 seconds**
- **Persistent storage** for metrics (15 days retention)
- **NodePort access** - No ingress required

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│              Sipeed CM5 Cluster                      │
├─────────────────────────────────────────────────────┤
│                                                       │
│  ┌──────────────┐         ┌──────────────┐         │
│  │ Control Node │         │ Worker Nodes │         │
│  │  (Slot 1)    │         │  (Slots 2-7) │         │
│  ├──────────────┤         ├──────────────┤         │
│  │ Fan Control  │         │ Temp Export  │         │
│  │ :2506/status │         │ :2505/metrics│         │
│  │ :2506/metrics│         │              │         │
│  └───────┬──────┘         └──────┬───────┘         │
│          │                       │                   │
│          └───────────┬───────────┘                   │
│                      ▼                               │
│              ┌───────────────┐                       │
│              │  Prometheus   │                       │
│              │  Scrapes data │                       │
│              │  every 15s    │                       │
│              └───────┬───────┘                       │
│                      │                               │
│                      ▼                               │
│              ┌───────────────┐                       │
│              │    Grafana    │                       │
│              │   Dashboard   │                       │
│              │  Port: 30300  │                       │
│              └───────────────┘                       │
│                                                       │
└─────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

1. **Fan control system must be installed first**
   ```bash
   cd ../deploy-kubernetes
   ./install.sh sipeed-cm5-fancontrol
   ```

2. **Helm 3.x** installed on your system

3. **kubectl** configured to access your cluster

4. **k3s default storage class** (`local-path`) for persistent volumes

## 🚀 Installation

### Quick Install

```bash
cd deploy-monitoring
./install.sh [namespace]
```

If no namespace is specified, it defaults to `sipeed-cm5-fancontrol`.

### Manual Install

```bash
helm install sipeed-monitoring ./helm \
  --namespace sipeed-cm5-fancontrol \
  --create-namespace
```

## 🌐 Accessing Grafana

### 1. Get Node IP

```bash
kubectl get nodes -o wide
```

Example output:
```
NAME           STATUS   ROLES                  AGE   VERSION        INTERNAL-IP
cm5-slot1      Ready    control-plane,master   5d    v1.28.2+k3s1   192.168.1.101
cm5-slot2      Ready    <none>                 5d    v1.28.2+k3s1   192.168.1.102
```

### 2. Access Grafana

Open your browser to: **`http://<NODE-IP>:30300`**

Example: `http://192.168.1.101:30300`

### 3. Login

- **Username:** `admin`
- **Password:** `admin123`

⚠️ **Change the default password immediately after first login!**

### 4. View Dashboard

The dashboard **"Sipeed CM5 - Temperature & Fan Control"** is automatically loaded.

You can find it at: **Home → Dashboards → Sipeed CM5 - Temperature & Fan Control**

## 📊 Dashboard Panels

### 1. CPU Temperature per Node (Time Series)
- Shows temperature trends for all nodes
- Color-coded by node hostname
- Displays last, max, and mean values in legend
- Yellow threshold at 60°C, red at 75°C

### 2. Current Fan Speed (Gauge)
- Real-time fan speed percentage (0-100%)
- Green: 0-50%, Yellow: 50-80%, Red: 80-100%
- Large, easy-to-read display

### 3. Fan Speed History (Time Series)
- Historical fan speed over time
- Shows how fan responds to temperature changes
- Useful for analyzing fan curve behavior

### 4. Current Temperatures - All Nodes (Bar Chart)
- Horizontal bars showing current temp for each node
- Quick at-a-glance view of cluster thermal status
- Color-coded thresholds

## ⚙️ Configuration

### Customize Values

Edit `helm/values.yaml` to customize:

```yaml
# Change Grafana admin credentials
grafana:
  adminUser: admin
  adminPassword: your-secure-password
  
# Adjust scrape interval
prometheus:
  scrapeInterval: 15s  # How often to collect metrics
  
# Change retention period
prometheus:
  retention: 15d  # Keep data for 15 days
  
# Adjust storage sizes
prometheus:
  persistence:
    size: 8Gi  # Prometheus data storage
    
grafana:
  persistence:
    size: 2Gi  # Grafana config storage
```

### Apply Changes

```bash
helm upgrade sipeed-monitoring ./helm \
  --namespace sipeed-cm5-fancontrol \
  -f helm/values.yaml
```

Or use `--set`:

```bash
helm upgrade sipeed-monitoring ./helm \
  --namespace sipeed-cm5-fancontrol \
  --set grafana.adminPassword=MyNewPassword123
```

## 🔍 Metrics Collected

### Temperature Exporter (`:2505/metrics`)

- `node_temperature_celsius` - CPU temperature in Celsius
  - Label: `instance` (node hostname)
  - Label: `node` (node name)

### Fan Controller (`:2506/metrics`)

- `fan_duty_percent` - Fan speed percentage (0-100)
- `aggregate_temperature_celsius` - Aggregated temperature from all nodes
- `fan_controller_running` - Controller status (1=running, 0=stopped)

## 🔧 Troubleshooting

### Grafana shows "No data"

1. Check if Prometheus is scraping targets:
   ```bash
   kubectl port-forward -n sipeed-cm5-fancontrol svc/sipeed-prometheus 9090:9090
   ```
   Then visit `http://localhost:9090/targets`

2. Verify fan control pods are running:
   ```bash
   kubectl get pods -n sipeed-cm5-fancontrol
   ```

3. Test metrics endpoints manually:
   ```bash
   # Test temp exporter
   kubectl run -it --rm debug --image=alpine --restart=Never -- \
     wget -qO- http://sipeed-temp-exporter:2505/metrics
   
   # Test fan controller
   kubectl run -it --rm debug --image=alpine --restart=Never -- \
     wget -qO- http://sipeed-fan-controller:2506/metrics
   ```

### Prometheus pod crashes

Check logs:
```bash
kubectl logs -n sipeed-cm5-fancontrol -l app=prometheus
```

Common issues:
- **Out of disk space:** Increase PVC size in `values.yaml`
- **Config error:** Validate `prometheus.yml` syntax

### Grafana won't start

Check logs:
```bash
kubectl logs -n sipeed-cm5-fancontrol -l app=grafana
```

Check PVC status:
```bash
kubectl get pvc -n sipeed-cm5-fancontrol
```

### Can't access Grafana on port 30300

1. Verify service is created:
   ```bash
   kubectl get svc -n sipeed-cm5-fancontrol grafana
   ```

2. Check if NodePort is allocated:
   ```bash
   kubectl describe svc -n sipeed-cm5-fancontrol grafana
   ```

3. Test from within cluster:
   ```bash
   kubectl run -it --rm debug --image=alpine --restart=Never -- \
     wget -qO- http://grafana:3000
   ```

## 🗑️ Uninstallation

```bash
helm uninstall sipeed-monitoring -n sipeed-cm5-fancontrol
```

To also delete persistent volumes:

```bash
kubectl delete pvc -n sipeed-cm5-fancontrol grafana-data prometheus-data
```

## 📚 Additional Resources

### Prometheus Queries

Access Prometheus UI:
```bash
kubectl port-forward -n sipeed-cm5-fancontrol svc/sipeed-prometheus 9090:9090
```

Useful queries:
```promql
# Average temperature across all nodes
avg(node_temperature_celsius)

# Maximum temperature
max(node_temperature_celsius)

# Temperature of specific node
node_temperature_celsius{instance="cm5-slot2"}

# Fan speed over last hour
fan_duty_percent[1h]
```

### Creating Custom Dashboards

1. In Grafana, click **"+" → Dashboard**
2. Add panels with these queries:
   - `node_temperature_celsius` - Temperature per node
   - `fan_duty_percent` - Fan speed
   - `aggregate_temperature_celsius` - Aggregate temp
3. Save dashboard

### Alerting (Advanced)

Configure Grafana alerts:
1. Go to **Alerting → Alert rules**
2. Create alert for high temperature:
   - Query: `max(node_temperature_celsius) > 75`
   - Condition: Alert when above threshold for > 5 minutes

## 🔐 Security Notes

1. **Change default password** immediately after installation
2. Consider using **Ingress with TLS** instead of NodePort for production
3. Restrict network access to port 30300 using firewall rules
4. Use **secrets** for Grafana credentials instead of plain text in `values.yaml`

## 📝 License

This monitoring stack is part of the Sipeed CM5 Fan Control project, licensed under the MIT License.

## 🤝 Contributing

Issues and pull requests are welcome at the main repository:
https://github.com/Mi-Q/sipeed-cm5-fancontrol
