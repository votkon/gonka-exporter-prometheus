# Gonka Prometheus Exporter

Exports metrics from Gonka blockchain node and ML admin API for Prometheus.

## Metrics Exposed

| Metric | Description |
|--------|-------------|
| `gonka_block_height` | Latest block height |
| `gonka_block_time_seconds` | Timestamp of latest block |
| `gonka_node_status` | Node status (0=other, 1=INFERENCE, 2=POC) |
| `gonka_node_poc_weight` | POC weight per node |

## Requirements

- Access to `localhost:26657/status` (Tendermint RPC)
- Access to `localhost:9200/admin/v1/nodes` (ML Admin API)

## Deployment

### Build and run:

```bash
cd ~/gonka-exporter
docker build -t gonka-exporter .
docker run -d \
  --name gonka-exporter \
  --network host \
  --restart unless-stopped \
  gonka-exporter
```

### Open firewall for Prometheus server:

```bash
sudo ufw allow from YOUR.PROMETHEUS.SERVER.IP to any port 9401
```

### Test:

```bash
curl http://localhost:9401/metrics
```

## Update

```bash
cd ~/gonka-exporter
git pull
docker stop gonka-exporter && docker rm gonka-exporter
docker build -t gonka-exporter .
docker run -d \
  --name gonka-exporter \
  --network host \
  --restart unless-stopped \
  gonka-exporter
```

## Prometheus Config

Add to `prometheus.yml`:

```yaml
  - job_name: 'gonka'
    static_configs:
      - targets:
          - '1.1.1.1:9401'  

```
