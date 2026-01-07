# Gonka Prometheus Exporter

A comprehensive Prometheus exporter for the Gonka blockchain network that provides metrics for network-wide monitoring, node performance, participant statistics, and blockchain health.

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Metrics Overview](#metrics-overview)
- [Installation](#installation)
- [Deployment](#deployment)
  - [Central Network Monitoring](#central-network-monitoring)
  - [Local Node Monitoring](#local-node-monitoring)
- [Configuration](#configuration)
- [Prometheus Configuration](#prometheus-configuration)
- [Troubleshooting](#troubleshooting)

---

## Features

- ✅ **Network-wide monitoring** - Track all participants, pricing, and models across the entire Gonka network
- ✅ **Blockchain metrics** - Block height, block time, chain status from multiple nodes for reliability
- ✅ **Node performance** - GPU utilization, node status, PoC weights, intended vs current state
- ✅ **Participant statistics** - Earnings, inferences, validations, missed requests per epoch
- ✅ **Flexible deployment** - Run as centralized network monitor or distributed node monitor
- ✅ **High availability** - Queries 3 external nodes for block height to ensure and maximum block height

---

## Architecture

### Deployment Modes

This exporter supports two deployment modes:

#### 1. **Central Network Monitoring** (`EXPORT_NETWORK_METRICS=true`)
- Runs on **one dedicated monitoring server**
- Exports network-wide metrics (all participants, pricing, models)
- Queries 3 public nodes (`node1`, `node2`, `node3.gonka.ai`) for block height (takes maximum)
- Uses local `localhost:8000` for other network data to reduce load on public nodes
- **Does not** monitor local node hardware

#### 2. **Local Node Monitoring** (`EXPORT_NETWORK_METRICS=false`)
- Runs on **each of your validator/host nodes** (all 5+ nodes)
- Exports local node metrics (status, GPU stats, PoC weights)
- Exports participant-specific stats (your earnings, validations, etc.)
- Queries local Tendermint RPC (`localhost:26657`)
- **Does not** export duplicate network-wide data

---

## Metrics Overview

### Blockchain Metrics (Always Exported)

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_block_height` | Latest block height | - | Tendermint RPC or 3 public nodes (max) |
| `gonka_block_time_seconds` | Latest block timestamp (Unix epoch) | - | Tendermint RPC or public nodes |
| `gonka_chain_earliest_block_height` | Earliest block in chain | - | Tendermint RPC or public nodes |
| `gonka_chain_earliest_block_time` | Earliest block timestamp | - | Tendermint RPC or public nodes |
| `gonka_chain_catching_up` | Whether node is syncing (1) or synced (0) | - | Tendermint RPC or public nodes |

**Data Source:**
- **Network mode**: Queries `http://node1.gonka.ai:8000`, `http://node2.gonka.ai:8000`, `http://node3.gonka.ai:8000` for block height (takes max)
- **Local mode**: Queries `http://localhost:26657/status` (Tendermint RPC)

---

### Network-Wide Metrics (Only if `EXPORT_NETWORK_METRICS=true`)

#### Participant Metrics

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_network_participant_weight` | Weight of each participant in the network | `participant` | `/v1/epochs/current/participants` |
| `gonka_network_node_poc_weight` | PoC weight per node across network | `participant`, `node_id` | `/v1/epochs/current/participants` |

**Data Source:** `http://localhost:8000/v1/epochs/current/participants`

#### Pricing Metrics

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_pricing_unit_of_compute_price` | Base unit of compute price | - | `/v1/pricing` |
| `gonka_pricing_dynamic_enabled` | Dynamic pricing enabled (1=yes, 0=no) | - | `/v1/pricing` |
| `gonka_pricing_model_price_per_token` | Price per token for each model | `model_id` | `/v1/pricing` |
| `gonka_pricing_model_units_per_token` | Compute units per token | `model_id` | `/v1/pricing` |

**Data Source:** `http://localhost:8000/v1/pricing`

#### Model Metrics

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_model_v_ram` | VRAM requirement in GB | `model_id` | `/v1/models` |
| `gonka_model_throughput_per_nonce` | Throughput per nonce | `model_id` | `/v1/models` |
| `gonka_model_validation_threshold` | Validation threshold (value × 10^exponent) | `model_id` | `/v1/models` |

**Data Source:** `http://localhost:8000/v1/models`

---

### Participant-Specific Metrics (Only if `PARTICIPANT_ADDRESS` is set)

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_participant_epochs_completed` | Total epochs completed | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_coin_balance` | Current coin balance | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_inference_count` | Inferences processed this epoch | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_missed_requests` | Missed requests this epoch | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_earned_coins` | Coins earned this epoch | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_validated_inferences` | Successful validations this epoch | `participant` | `/chain-api/.../participant/{address}` |
| `gonka_participant_invalidated_inferences` | Failed validations this epoch | `participant` | `/chain-api/.../participant/{address}` |

**Data Source:** `http://localhost:8000/chain-api/productscience/inference/inference/participant/{address}`

---

### Local Node Metrics (Only if `ENABLE_NODE_FETCH=true`)

| Metric | Description | Labels | Source |
|--------|-------------|--------|--------|
| `gonka_node_status` | Current node status (0-5, see enum below) | `node_id`, `host` | Admin API `/nodes` |
| `gonka_node_intended_status` | Intended/target node status | `node_id`, `host` | Admin API `/nodes` |
| `gonka_node_poc_weight` | PoC weight for this node | `node_id`, `host`, `model` | Admin API `/nodes` |
| `gonka_node_poc_current_status` | Current PoC status (0-2, see enum below) | `node_id`, `host` | Admin API `/nodes` |
| `gonka_node_poc_intended_status` | Intended PoC status | `node_id`, `host` | Admin API `/nodes` |
| `gonka_node_gpu_device_count` | Number of GPU devices | `node_id`, `host` | Node GPU API |
| `gonka_node_gpu_avg_utilization_percent` | Average GPU utilization % | `node_id`, `host` | Node GPU API |

**Node Status Enum:**
- `0` = UNKNOWN
- `1` = INFERENCE
- `2` = POC
- `3` = TRAINING
- `4` = STOPPED
- `5` = FAILED

**PoC Status Enum:**
- `0` = IDLE
- `1` = GENERATING
- `2` = VALIDATING

**Data Sources:**
- Node info: `http://localhost:9200/admin/v1/nodes`
- GPU stats: `http://{node_host}:{poc_port}/v3.0.8/api/v1/gpu/devices`

---

## Installation

### Prerequisites

- Docker installed on your server(s)
- Access to Gonka node endpoints:
  - Tendermint RPC: `localhost:26657` (for local monitoring)
  - Network API: `localhost:8000` (for network/participant data)
  - Admin API: `localhost:9200` (for node monitoring)
- Your Gonka participant address (starts with `gonka1...`)

### Clone the Repository
```bash
# Clone from GitHub
git clone https://github.com/votkon/gonka-exporter-prometheus.git
cd gonka-exporter-prometheus
```

### Build the Docker Image
```bash
docker build -t gonka-exporter .
```

---

## Deployment

### Central Network Monitoring

Deploy **once** on a dedicated monitoring server or on one of your nodes.

This instance will:
- ✅ Export network-wide metrics (all participants, pricing, models)
- ✅ Check 3 public nodes for block height (takes maximum for reliability)
- ✅ Export your participant statistics
- ❌ Will NOT monitor local node hardware
```bash
docker run -d \
  --name gonka-network-exporter \
  --network host \
  --restart unless-stopped \
  -e EXPORT_NETWORK_METRICS=true \
  -e ENABLE_NODE_FETCH=false \
  -e PARTICIPANT_ADDRESS=gonka1abc...youraddress \
  -e EXPORTER_PORT=9401 \
  -e REFRESH_INTERVAL=30 \
  gonka-exporter
```

**Verify:**
```bash
# Check logs
docker logs gonka-network-exporter

# Test metrics endpoint
curl http://localhost:9401/metrics | grep "gonka_"

# Should see network metrics like:
# gonka_network_participant_weight{participant="..."} 
# gonka_pricing_unit_of_compute_price
# gonka_participant_earned_coins{participant="..."}
```

---

### Combined Network + Node Monitoring

Deploy **once** on one of your validator/host nodes that will serve as both network monitor and local node monitor.

This instance will:
- ✅ Export network-wide metrics (all participants, pricing, models)
- ✅ Check 3 public nodes for block height (takes maximum for reliability)
- ✅ Export your participant statistics
- ✅ Export local node metrics (status, GPU, PoC weights) for THIS node
- ✅ Best for consolidating monitoring on one primary node
```bash
docker run -d \
  --name gonka-combined-exporter \
  --network host \
  --restart unless-stopped \
  -e EXPORT_NETWORK_METRICS=true \
  -e ENABLE_NODE_FETCH=true \
  -e PARTICIPANT_ADDRESS=gonka1abc...youraddress \
  -e GONKA_BASE_URL=http://localhost:26657 \
  -e NODE_BASE_URL=http://localhost:9200/admin/v1 \
  -e EXPORTER_PORT=9401 \
  -e REFRESH_INTERVAL=30 \
  gonka-exporter
```

**Verify:**
```bash
# Check logs
docker logs gonka-combined-exporter

# Test metrics endpoint
curl http://localhost:9401/metrics | grep "gonka_"

# Should see BOTH network and local metrics like:
# gonka_network_participant_weight{participant="..."}  # Network-wide
# gonka_pricing_unit_of_compute_price                  # Network-wide
# gonka_node_status{node_id="...",host="..."}          # Local node
# gonka_node_gpu_device_count{node_id="...",host="..."} # Local node
# gonka_participant_earned_coins{participant="..."}    # Your stats
```

**Use Case:** Deploy this on your primary/main validator node. Then deploy "Local Node Monitoring" (below) on your remaining nodes to avoid duplicating network-wide metrics.

---

### Local Node Monitoring

Deploy on **each of your remaining validator/host nodes** (nodes 2-5 if node 1 uses combined monitoring).

Each instance will:
- ✅ Export local node metrics (status, GPU, PoC weights)
- ✅ Export your participant statistics for this address
- ✅ Export local blockchain data
- ❌ Will NOT export duplicate network-wide data
```bash
docker run -d \
  --name gonka-node-exporter \
  --network host \
  --restart unless-stopped \
  -e EXPORT_NETWORK_METRICS=false \
  -e ENABLE_NODE_FETCH=true \
  -e PARTICIPANT_ADDRESS=gonka1abc...youraddress \
  -e GONKA_BASE_URL=http://localhost:26657 \
  -e NODE_BASE_URL=http://localhost:9200/admin/v1 \
  -e EXPORTER_PORT=9401 \
  -e REFRESH_INTERVAL=30 \
  gonka-exporter
```

**Verify:**
```bash
# Check logs
docker logs gonka-node-exporter

# Test metrics endpoint
curl http://localhost:9401/metrics | grep "gonka_"

# Should see local metrics like:
# gonka_node_status{node_id="...",host="..."}
# gonka_node_gpu_device_count{node_id="...",host="..."}
# gonka_participant_inference_count{participant="..."}
```

---

### Deployment Strategy Comparison

| Deployment Type | Network Metrics | Local Node Metrics | Use Case |
|-----------------|----------------|-------------------|----------|
| **Central Network Monitoring** | ✅ | ❌ | Dedicated monitoring server with no validator |
| **Combined Monitoring** | ✅ | ✅ | Primary validator node (node 1 of 5) |
| **Local Node Monitoring** | ❌ | ✅ | Secondary validator nodes (nodes 2-5) |

**Recommended Setup for 5 Nodes:**
- **Node 1**: Combined monitoring (`EXPORT_NETWORK_METRICS=true`, `ENABLE_NODE_FETCH=true`)
- **Nodes 2-5**: Local monitoring only (`EXPORT_NETWORK_METRICS=false`, `ENABLE_NODE_FETCH=true`)

This ensures network-wide metrics are scraped once, while each node reports its own hardware metrics.
---

## Configuration

All configuration is done via environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `EXPORT_NETWORK_METRICS` | Enable network-wide metrics (true/false) | `false` | No |
| `ENABLE_NODE_FETCH` | Enable local node monitoring (true/false) | `true` | No |
| `PARTICIPANT_ADDRESS` | Your Gonka participant address (gonka1...) | *(empty)* | Recommended |
| `GONKA_BASE_URL` | Tendermint RPC URL for local monitoring | `http://localhost:26657` | No |
| `NODE_BASE_URL` | Admin API URL for node monitoring | `http://localhost:9200/admin/v1` | No |
| `EXPORTER_PORT` | Port to expose Prometheus metrics | `9401` | No |
| `REFRESH_INTERVAL` | Seconds between metric updates | `30` | No |

---

## Prometheus Configuration

Add to your `prometheus.yml`:

### For Central Network Monitoring
```yaml
scrape_configs:
  - job_name: 'gonka-network'
    static_configs:
      - targets:
          - 'monitoring-server.example.com:9401'
        labels:
          instance: 'network'
          type: 'network-monitor'
```

### For Local Node Monitoring
```yaml
scrape_configs:
  - job_name: 'gonka-nodes'
    static_configs:
      - targets:
          - 'node1.example.com:9401'
          - 'node2.example.com:9401'
          - 'node3.example.com:9401'
          - 'node4.example.com:9401'
          - 'node5.example.com:9401'
        labels:
          type: 'node-monitor'
```

### Combined Configuration
```yaml
scrape_configs:
  # Network-wide metrics (scraped once)
  - job_name: 'gonka-network'
    static_configs:
      - targets: ['monitoring-server:9401']
        labels:
          type: 'network'
    scrape_interval: 30s

  # Per-node metrics (scraped from each node)
  - job_name: 'gonka-nodes'
    static_configs:
      - targets:
          - 'node1:9401'
          - 'node2:9401'
          - 'node3:9401'
        labels:
          type: 'node'
    scrape_interval: 30s
```

---

## Updating the Exporter
```bash
# Navigate to repository
cd ~/gonka-exporter-prometheus

# Pull latest changes
git pull

# Stop and remove old container
docker stop gonka-network-exporter  # or gonka-node-exporter
docker rm gonka-network-exporter

# Rebuild image
docker build -t gonka-exporter .

# Run with same configuration as before
docker run -d \
  --name gonka-network-exporter \
  --network host \
  --restart unless-stopped \
  -e EXPORT_NETWORK_METRICS=true \
  -e PARTICIPANT_ADDRESS=gonka1abc...youraddress \
  gonka-exporter
```

---

## Troubleshooting

### Container won't start
```bash
# Check container status
docker ps -a | grep gonka

# View logs
docker logs gonka-network-exporter
```

**Common issues:**
- Missing `requirements.txt` - rebuild image
- Port 9401 already in use - change `EXPORTER_PORT`

### Connection refused errors
```
[ERROR] Failed to fetch participants from http://localhost:8000...
```

**Solution:** Make sure you're using `--network host`:
```bash
docker run -d --name gonka-exporter --network host ...
```

Without `--network host`, the container can't reach `localhost` services on your host.

### No metrics showing
```bash
# Check if metrics endpoint is accessible
curl http://localhost:9401/metrics

# Check for errors in logs
docker logs gonka-network-exporter | grep ERROR
```

### GPU metrics not showing

**Requirements:**
- `ENABLE_NODE_FETCH=true`
- `NODE_BASE_URL` must be set
- GPU API must be accessible: `http://{node_host}:{poc_port}/v3.0.8/api/v1/gpu/devices`

### Block height stuck or incorrect

**For network monitoring:**
- Checks 3 public nodes and takes maximum
- If all 3 nodes fail, block height won't update
- Check logs for connection errors to `node1`, `node2`, `node3.gonka.ai`

**For local monitoring:**
- Ensure Tendermint RPC is accessible: `curl http://localhost:26657/status`

---

## Firewall Configuration

If your Prometheus server is remote:
```bash
# Allow Prometheus to scrape metrics
sudo ufw allow from PROMETHEUS_SERVER_IP to any port 9401

# Or allow from entire subnet
sudo ufw allow from 10.0.0.0/24 to any port 9401
```

---

## Example Grafana Queries

### Network Health
```promql
# Current block height
gonka_block_height

# Block production rate (blocks per minute)
rate(gonka_block_height[5m]) * 60

# Is node synced?
gonka_chain_catching_up == 0
```

### Participant Performance
```promql
# Your earnings this epoch
gonka_participant_earned_coins{participant="gonka1abc..."}

# Your inference success rate
gonka_participant_validated_inferences{participant="gonka1abc..."} 
/ 
(gonka_participant_validated_inferences{participant="gonka1abc..."} + gonka_participant_invalidated_inferences{participant="gonka1abc..."})

# Missed requests
gonka_participant_missed_requests{participant="gonka1abc..."}
```

### Node Performance
```promql
# GPU utilization
gonka_node_gpu_avg_utilization_percent

# Node status (1=INFERENCE, 2=POC)
gonka_node_status

# Status drift detection (current != intended)
gonka_node_status != gonka_node_intended_status
```

### Network Economics
```promql
# Current pricing
gonka_pricing_unit_of_compute_price

# Model pricing
gonka_pricing_model_price_per_token

# Total network weight
sum(gonka_network_participant_weight)
```

---

## License

This project is open-source and distributed under the MIT License.

---

## Support

For issues, questions, or contributions:
- GitHub Issues: https://github.com/votkon/gonka-exporter-prometheus/issues
- Gonka Discord: https://discord.gg/gonka
