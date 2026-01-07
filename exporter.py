import os
import time
import json
import requests
import random
from prometheus_client import start_http_server, Gauge
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, timezone

# =============================================================================
# CONFIGURATION
# =============================================================================

# Base URLs
BASE_URL = os.getenv("GONKA_BASE_URL", "http://localhost:26657").rstrip("/")
NODE_BASE_URL = os.getenv("NODE_BASE_URL", "http://localhost:9200/admin/v1").rstrip("/")

# Network API URL (always localhost to reduce load on external nodes)
NETWORK_API_URL = "http://localhost:8000"

# Block height nodes - check multiple for reliability when doing network monitoring
BLOCK_HEIGHT_NODES = [
    "http://node1.gonka.ai:8000",
    "http://node2.gonka.ai:8000",
    "http://node3.gonka.ai:8000",
    "http://185.216.21.98:8000",
    "http://36.189.234.197:18026",
    "http://36.189.234.237:17241",
    "http://47.236.26.199:8000",
    "http://47.236.19.22:18000",
    "http://gonka.spv.re:8000",
]

# Feature flags
EXPORT_NETWORK_METRICS = os.getenv("EXPORT_NETWORK_METRICS", "false").lower() in ("1", "true", "yes")
ENABLE_NODE_FETCH = os.getenv("ENABLE_NODE_FETCH", "true").lower() in ("1", "true", "yes")

# Optional participant address for detailed stats
PARTICIPANT_ADDRESS = os.getenv("PARTICIPANT_ADDRESS", "").strip()

# Exporter settings
EXPORTER_PORT = int(os.getenv("EXPORTER_PORT", "9401"))
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "30"))

# API endpoints
TENDERMINT_STATUS_ENDPOINT = "/status"
PARTICIPANTS_ENDPOINT = "/v1/epochs/current/participants"
PRICING_ENDPOINT = "/v1/pricing"
MODELS_ENDPOINT = "/v1/models"
CHAIN_STATUS_ENDPOINT = "/chain-rpc/status"
PARTICIPANT_STATS_ENDPOINT = "/chain-api/productscience/inference/inference/participant"

# Enum mappings
HARDWARE_NODE_STATUS_MAP = {
    "UNKNOWN": 0,
    "INFERENCE": 1,
    "POC": 2,
    "TRAINING": 3,
    "STOPPED": 4,
    "FAILED": 5,
}

POC_STATUS_MAP = {
    "IDLE": 0,
    "GENERATING": 1,
    "VALIDATING": 2,
}

# =============================================================================
# PROMETHEUS METRICS - ORIGINAL (BACKWARD COMPATIBLE)
# =============================================================================
# Add this new metric in the PROMETHEUS METRICS section (around line 70):

BLOCK_HEIGHT_MAX = Gauge(
    "gonka_block_height_max",
    "Maximum block height from 3 public Gonka nodes (network monitoring only)"
)

BLOCK_HEIGHT = Gauge(
    "gonka_block_height",
    "Latest block height from Tendermint RPC"
)

BLOCK_TIME = Gauge(
    "gonka_block_time_seconds",
    "Timestamp of latest block (seconds since epoch)"
)

NODE_STATUS = Gauge(
    "gonka_node_status",
    "Node status (0=other, 1=INFERENCE, 2=POC, 3=TRAINING, 4=STOPPED, 5=FAILED)",
    ["node_id", "host"]
)

NODE_POC_WEIGHT = Gauge(
    "gonka_node_poc_weight",
    "POC weight per node",
    ["node_id", "host", "model"]
)

# =============================================================================
# PROMETHEUS METRICS - NETWORK-WIDE (CONDITIONAL)
# =============================================================================

NETWORK_PARTICIPANT_WEIGHT = Gauge(
    "gonka_network_participant_weight",
    "Weight of each participant in the network",
    ["participant"]
)

NETWORK_NODE_POC_WEIGHT = Gauge(
    "gonka_network_node_poc_weight",
    "PoC weight of a node across the network",
    ["participant", "node_id"]
)

# =============================================================================
# PROMETHEUS METRICS - PRICING (CONDITIONAL)
# =============================================================================

PRICING_UNIT_OF_COMPUTE_PRICE = Gauge(
    "gonka_pricing_unit_of_compute_price",
    "Unit of compute price from pricing endpoint"
)

PRICING_DYNAMIC_ENABLED = Gauge(
    "gonka_pricing_dynamic_enabled",
    "Dynamic pricing enabled flag (1 = true, 0 = false)"
)

PRICING_MODEL_PRICE = Gauge(
    "gonka_pricing_model_price_per_token",
    "Price per token for each model",
    ["model_id"]
)

PRICING_MODEL_UNITS = Gauge(
    "gonka_pricing_model_units_per_token",
    "Units of compute per token for each model",
    ["model_id"]
)

# =============================================================================
# PROMETHEUS METRICS - MODELS (CONDITIONAL)
# =============================================================================

MODEL_V_RAM = Gauge(
    "gonka_model_v_ram",
    "VRAM requirement for each model in GB",
    ["model_id"]
)

MODEL_THROUGHPUT = Gauge(
    "gonka_model_throughput_per_nonce",
    "Throughput per nonce for each model",
    ["model_id"]
)

MODEL_VALIDATION_THRESHOLD = Gauge(
    "gonka_model_validation_threshold",
    "Validation threshold (value * 10^exponent)",
    ["model_id"]
)

# =============================================================================
# PROMETHEUS METRICS - PARTICIPANT STATS (CONDITIONAL)
# =============================================================================

PARTICIPANT_EPOCHS_COMPLETED = Gauge(
    "gonka_participant_epochs_completed",
    "Number of epochs completed by participant",
    ["participant"]
)

PARTICIPANT_COIN_BALANCE = Gauge(
    "gonka_participant_coin_balance",
    "Coin balance of participant",
    ["participant"]
)

PARTICIPANT_INFERENCE_COUNT = Gauge(
    "gonka_participant_inference_count",
    "Inference count for participant in current epoch",
    ["participant"]
)

PARTICIPANT_MISSED_REQUESTS = Gauge(
    "gonka_participant_missed_requests",
    "Missed requests for participant in current epoch",
    ["participant"]
)

PARTICIPANT_EARNED_COINS = Gauge(
    "gonka_participant_earned_coins",
    "Earned coins for participant in current epoch",
    ["participant"]
)

PARTICIPANT_VALIDATED_INFERENCES = Gauge(
    "gonka_participant_validated_inferences",
    "Validated inferences for participant in current epoch",
    ["participant"]
)

PARTICIPANT_INVALIDATED_INFERENCES = Gauge(
    "gonka_participant_invalidated_inferences",
    "Invalidated inferences for participant in current epoch",
    ["participant"]
)

# =============================================================================
# PROMETHEUS METRICS - ENHANCED NODE METRICS
# =============================================================================

NODE_INTENDED_STATUS = Gauge(
    "gonka_node_intended_status",
    "Intended status of node (target state)",
    ["node_id", "host"]
)

NODE_POC_CURRENT_STATUS = Gauge(
    "gonka_node_poc_current_status",
    "Current POC status (0=IDLE, 1=GENERATING, 2=VALIDATING)",
    ["node_id", "host"]
)

NODE_POC_INTENDED_STATUS = Gauge(
    "gonka_node_poc_intended_status",
    "Intended POC status (target state)",
    ["node_id", "host"]
)

NODE_GPU_DEVICE_COUNT = Gauge(
    "gonka_node_gpu_device_count",
    "Number of GPU devices on node",
    ["node_id", "host"]
)

NODE_GPU_AVG_UTILIZATION = Gauge(
    "gonka_node_gpu_avg_utilization_percent",
    "Average GPU utilization percent across all devices",
    ["node_id", "host"]
)

# =============================================================================
# PROMETHEUS METRICS - ENHANCED CHAIN METRICS
# =============================================================================

EARLIEST_BLOCK_HEIGHT = Gauge(
    "gonka_chain_earliest_block_height",
    "Earliest block height in chain"
)

EARLIEST_BLOCK_TIME = Gauge(
    "gonka_chain_earliest_block_time",
    "Earliest block timestamp (seconds since epoch)"
)

CATCHING_UP = Gauge(
    "gonka_chain_catching_up",
    "Whether node is catching up (1) or synced (0)"
)

# =============================================================================
# FETCH FUNCTIONS
# =============================================================================

def fetch_tendermint_status() -> Optional[Dict[str, Any]]:
    """
    Fetch status from local Tendermint RPC endpoint.
    Returns parsed JSON or None on failure.
    """
    url = f"{BASE_URL}{TENDERMINT_STATUS_ENDPOINT}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {})
    except Exception as exc:
        print(f"[ERROR] Failed to fetch Tendermint status from {url}: {exc}")
        return None


def fetch_chain_status_from_node(node_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch chain status from a specific node.
    Returns parsed JSON or None on failure.
    """
    url = f"{node_url}{CHAIN_STATUS_ENDPOINT}"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get("result", {})
    except Exception as exc:
        print(f"[ERROR] Failed to fetch chain status from {url}: {exc}")
        return None


def fetch_max_block_height_from_nodes() -> Optional[Tuple[int, str]]:
    """
    Fetch block height from localhost + 5 random external nodes and return the maximum.
    Returns (max_height, latest_time) or None if all nodes fail.
    """
    max_height = None
    latest_time = None
    
    # Always include localhost
    nodes_to_check = ["http://localhost:8000"]
    
    # Add 5 random nodes from the external list
    selected_external = random.sample(BLOCK_HEIGHT_NODES, min(5, len(BLOCK_HEIGHT_NODES)))
    nodes_to_check.extend(selected_external)
    
    for node_url in nodes_to_check:
        status = fetch_chain_status_from_node(node_url, timeout=2)
        if not status:
            continue
        
        sync_info = status.get("sync_info", {})
        height_str = sync_info.get("latest_block_height")
        time_str = sync_info.get("latest_block_time")
        
        if height_str:
            try:
                height = int(height_str)
                if max_height is None or height > max_height:
                    max_height = height
                    latest_time = time_str
            except Exception as exc:
                print(f"[ERROR] Failed to parse block height from {node_url}: {exc}")
    
    if max_height is not None:
        return max_height, latest_time
    
    return None

def fetch_participants() -> Optional[Dict[str, Any]]:
    """
    Fetch participants data from local network API.
    Returns parsed JSON or None on failure.
    """
    url = f"{NETWORK_API_URL}{PARTICIPANTS_ENDPOINT}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch participants from {url}: {exc}")
        return None


def fetch_pricing() -> Optional[Dict[str, Any]]:
    """
    Fetch pricing data from local network API.
    Returns parsed JSON or None on failure.
    """
    url = f"{NETWORK_API_URL}{PRICING_ENDPOINT}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch pricing from {url}: {exc}")
        return None


def fetch_models() -> Optional[Dict[str, Any]]:
    """
    Fetch models data from local network API.
    Returns parsed JSON or None on failure.
    """
    url = f"{NETWORK_API_URL}{MODELS_ENDPOINT}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch models from {url}: {exc}")
        return None


def fetch_participant_stats(address: str) -> Optional[Dict[str, Any]]:
    """
    Fetch detailed stats for a specific participant from local network API.
    Returns parsed JSON or None on failure.
    """
    url = f"{NETWORK_API_URL}{PARTICIPANT_STATS_ENDPOINT}/{address}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch participant stats for {address}: {exc}")
        return None


def fetch_nodes() -> List[Dict[str, Any]]:
    """
    Fetch list of nodes from admin API.
    Returns list of node dicts or empty list on failure.
    """
    url = f"{NODE_BASE_URL}/nodes"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        print(f"[ERROR] Failed to fetch nodes from {url}: {exc}")
        return []


def fetch_gpu_stats(host: str, port: int) -> Tuple[int, float]:
    """
    Fetch GPU device statistics from a node.
    Returns (device_count, avg_utilization_percent).
    On error, returns (0, 0.0).
    """
    api_version = "v3.0.8"
    url = f"http://{host}:{port}/{api_version}/api/v1/gpu/devices"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        devices = data.get("devices", [])
        count = len(devices)
        if count == 0:
            return 0, 0.0
        total_util = sum(d.get("utilization_percent", 0) for d in devices if isinstance(d, dict))
        avg_util = total_util / count
        return count, avg_util
    except Exception as exc:
        print(f"[ERROR] Failed to fetch GPU stats from {url}: {exc}")
        return 0, 0.0

# =============================================================================
# UPDATE FUNCTIONS
# =============================================================================

def update_tendermint_metrics():
    """
    Update basic Tendermint blockchain metrics.
    
    If EXPORT_NETWORK_METRICS is enabled:
        - Fetches block height from 3 nodes and exports as gonka_block_height_max
        - Also fetches local block height and exports as gonka_block_height
    Otherwise:
        - Uses local Tendermint RPC for gonka_block_height
    """
    if EXPORT_NETWORK_METRICS:
        # Network monitoring mode: check multiple nodes for max block height
        result = fetch_max_block_height_from_nodes()
        if result:
            max_height, latest_time = result
            BLOCK_HEIGHT_MAX.set(max_height)  # Export as separate metric
            
            if latest_time:
                try:
                    dt = datetime.fromisoformat(latest_time.rstrip("Z")).replace(tzinfo=timezone.utc)
                    BLOCK_TIME.set(dt.timestamp())
                except Exception as exc:
                    print(f"[ERROR] Failed to parse block time: {exc}")
        else:
            print("[WARN] Failed to fetch block height from all nodes")
        
        # Also fetch LOCAL node's block height
        local_status = fetch_tendermint_status()
        if local_status:
            sync_info = local_status.get("sync_info", {})
            
            local_height = sync_info.get("latest_block_height")
            if local_height:
                try:
                    BLOCK_HEIGHT.set(int(local_height))
                except Exception as exc:
                    print(f"[ERROR] Failed to parse local block height: {exc}")
            
            catching_up = sync_info.get("catching_up", False)
            CATCHING_UP.set(1 if catching_up else 0)
        
        # Also fetch enhanced metrics from first available public node
        for node_url in BLOCK_HEIGHT_NODES:
            status = fetch_chain_status_from_node(node_url)
            if status:
                sync_info = status.get("sync_info", {})
                
                earliest_height = sync_info.get("earliest_block_height")
                if earliest_height:
                    try:
                        EARLIEST_BLOCK_HEIGHT.set(int(earliest_height))
                    except Exception:
                        pass
                
                earliest_time = sync_info.get("earliest_block_time")
                if earliest_time:
                    try:
                        dt = datetime.fromisoformat(earliest_time.rstrip("Z")).replace(tzinfo=timezone.utc)
                        EARLIEST_BLOCK_TIME.set(dt.timestamp())
                    except Exception:
                        pass
                
                break  # Got data from one node, that's enough
    else:
        # Local monitoring mode: use local Tendermint RPC
        status = fetch_tendermint_status()
        if not status:
            return
        
        sync_info = status.get("sync_info", {})
        
        # Latest block height
        latest_height = sync_info.get("latest_block_height")
        if latest_height:
            try:
                BLOCK_HEIGHT.set(int(latest_height))
            except Exception as exc:
                print(f"[ERROR] Failed to parse latest_block_height: {exc}")
        
        # Latest block time
        latest_time = sync_info.get("latest_block_time")
        if latest_time:
            try:
                dt = datetime.fromisoformat(latest_time.rstrip("Z")).replace(tzinfo=timezone.utc)
                BLOCK_TIME.set(dt.timestamp())
            except Exception as exc:
                print(f"[ERROR] Failed to parse latest_block_time: {exc}")
        
        # Enhanced metrics
        earliest_height = sync_info.get("earliest_block_height")
        if earliest_height:
            try:
                EARLIEST_BLOCK_HEIGHT.set(int(earliest_height))
            except Exception:
                pass
        
        earliest_time = sync_info.get("earliest_block_time")
        if earliest_time:
            try:
                dt = datetime.fromisoformat(earliest_time.rstrip("Z")).replace(tzinfo=timezone.utc)
                EARLIEST_BLOCK_TIME.set(dt.timestamp())
            except Exception:
                pass
        
        catching_up = sync_info.get("catching_up", False)
        CATCHING_UP.set(1 if catching_up else 0)

def update_network_metrics():
    """
    Update network-wide metrics (participants across entire network).
    Always uses localhost:8000 to reduce load on external nodes.
    Only runs if EXPORT_NETWORK_METRICS is enabled.
    """
    if not EXPORT_NETWORK_METRICS:
        return
    
    data = fetch_participants()
    if not data:
        return
    
    participants = data.get("active_participants", {}).get("participants", [])
    
    for participant in participants:
        address = participant.get("seed", {}).get("participant")
        weight = participant.get("weight")
        
        if address and weight is not None:
            NETWORK_PARTICIPANT_WEIGHT.labels(participant=address).set(weight)
        
        # Network-wide node PoC weights
        for group in participant.get("ml_nodes", []):
            for node in group.get("ml_nodes", []):
                node_id = node.get("node_id")
                poc_weight = node.get("poc_weight")
                if address and node_id and poc_weight is not None:
                    NETWORK_NODE_POC_WEIGHT.labels(
                        participant=address,
                        node_id=node_id
                    ).set(poc_weight)


def update_pricing_metrics():
    """
    Update pricing metrics.
    Always uses localhost:8000 to reduce load on external nodes.
    Only runs if EXPORT_NETWORK_METRICS is enabled.
    """
    if not EXPORT_NETWORK_METRICS:
        return
    
    pricing = fetch_pricing()
    if not pricing:
        return
    
    # Unit price
    unit_price = pricing.get("unit_of_compute_price")
    if unit_price is not None:
        PRICING_UNIT_OF_COMPUTE_PRICE.set(unit_price)
    
    # Dynamic pricing flag
    dynamic_enabled = pricing.get("dynamic_pricing_enabled")
    if dynamic_enabled is not None:
        PRICING_DYNAMIC_ENABLED.set(1 if dynamic_enabled else 0)
    
    # Per-model pricing
    for model in pricing.get("models", []):
        model_id = model.get("id")
        if not model_id:
            continue
        
        price_per_token = model.get("price_per_token")
        if price_per_token is not None:
            PRICING_MODEL_PRICE.labels(model_id=model_id).set(price_per_token)
        
        units_per_token = model.get("units_of_compute_per_token")
        if units_per_token is not None:
            PRICING_MODEL_UNITS.labels(model_id=model_id).set(units_per_token)


def update_model_metrics():
    """
    Update model information metrics.
    Always uses localhost:8000 to reduce load on external nodes.
    Only runs if EXPORT_NETWORK_METRICS is enabled.
    """
    if not EXPORT_NETWORK_METRICS:
        return
    
    models = fetch_models()
    if not models:
        return
    
    for model in models.get("models", []):
        model_id = model.get("id")
        if not model_id:
            continue
        
        # VRAM
        v_ram = model.get("v_ram")
        if v_ram is not None:
            MODEL_V_RAM.labels(model_id=model_id).set(v_ram)
        
        # Throughput
        throughput = model.get("throughput_per_nonce")
        if throughput is not None:
            MODEL_THROUGHPUT.labels(model_id=model_id).set(throughput)
        
        # Validation threshold
        vt = model.get("validation_threshold", {})
        val_value = vt.get("value")
        val_exponent = vt.get("exponent")
        if val_value is not None and val_exponent is not None:
            try:
                combined = float(val_value) * (10 ** int(val_exponent))
                MODEL_VALIDATION_THRESHOLD.labels(model_id=model_id).set(combined)
            except Exception:
                pass


def update_participant_metrics():
    """
    Update participant-specific metrics (for YOUR address only).
    Always uses localhost:8000 to reduce load on external nodes.
    Only runs if PARTICIPANT_ADDRESS is set.
    """
    if not PARTICIPANT_ADDRESS:
        return
    
    p_data = fetch_participant_stats(PARTICIPANT_ADDRESS)
    if not p_data or not isinstance(p_data, dict):
        return
    
    participant = p_data.get("participant", {})
    
    # Epochs completed
    epochs = participant.get("epochs_completed")
    if epochs is not None:
        try:
            PARTICIPANT_EPOCHS_COMPLETED.labels(participant=PARTICIPANT_ADDRESS).set(int(epochs))
        except Exception:
            pass
    
    # Coin balance
    coin_balance = participant.get("coin_balance")
    if coin_balance is not None:
        try:
            PARTICIPANT_COIN_BALANCE.labels(participant=PARTICIPANT_ADDRESS).set(int(coin_balance))
        except Exception:
            pass
    
    # Current epoch stats
    epoch_stats = participant.get("current_epoch_stats", {})
    
    inference_count = epoch_stats.get("inference_count")
    if inference_count is not None:
        try:
            PARTICIPANT_INFERENCE_COUNT.labels(participant=PARTICIPANT_ADDRESS).set(int(inference_count))
        except Exception:
            pass
    
    missed_requests = epoch_stats.get("missed_requests")
    if missed_requests is not None:
        try:
            PARTICIPANT_MISSED_REQUESTS.labels(participant=PARTICIPANT_ADDRESS).set(int(missed_requests))
        except Exception:
            pass
    
    earned_coins = epoch_stats.get("earned_coins")
    if earned_coins is not None:
        try:
            PARTICIPANT_EARNED_COINS.labels(participant=PARTICIPANT_ADDRESS).set(int(earned_coins))
        except Exception:
            pass
    
    validated = epoch_stats.get("validated_inferences")
    if validated is not None:
        try:
            PARTICIPANT_VALIDATED_INFERENCES.labels(participant=PARTICIPANT_ADDRESS).set(int(validated))
        except Exception:
            pass
    
    invalidated = epoch_stats.get("invalidated_inferences")
    if invalidated is not None:
        try:
            PARTICIPANT_INVALIDATED_INFERENCES.labels(participant=PARTICIPANT_ADDRESS).set(int(invalidated))
        except Exception:
            pass


def update_node_metrics():
    """
    Update node-specific metrics (YOUR local nodes).
    Only runs if ENABLE_NODE_FETCH is true.
    """
    if not ENABLE_NODE_FETCH:
        return
    
    nodes = fetch_nodes()
    if not nodes:
        return
    
    for entry in nodes:
        node_info = entry.get("node", {})
        node_id = node_info.get("id", "unknown")
        node_host = node_info.get("host", "unknown")
        node_port = node_info.get("poc_port")
        
        state = entry.get("state", {})
        
        # Current status
        current_status = state.get("current_status", "").upper()
        status_value = HARDWARE_NODE_STATUS_MAP.get(current_status, 0)
        NODE_STATUS.labels(node_id=node_id, host=node_host).set(status_value)
        
        # Intended status
        intended_status = state.get("intended_status", "").upper()
        if intended_status:
            intended_value = HARDWARE_NODE_STATUS_MAP.get(intended_status, 0)
            NODE_INTENDED_STATUS.labels(node_id=node_id, host=node_host).set(intended_value)
        
        # PoC current status
        poc_status = state.get("poc_current_status", "").upper()
        poc_value = POC_STATUS_MAP.get(poc_status, 0)
        NODE_POC_CURRENT_STATUS.labels(node_id=node_id, host=node_host).set(poc_value)
        
        # PoC intended status
        poc_intended = state.get("poc_intended_status", "").upper()
        if poc_intended:
            poc_intended_value = POC_STATUS_MAP.get(poc_intended, 0)
            NODE_POC_INTENDED_STATUS.labels(node_id=node_id, host=node_host).set(poc_intended_value)
        
        # PoC weight per model
        epoch_ml_nodes = state.get("epoch_ml_nodes", {})
        for model, model_data in epoch_ml_nodes.items():
            if isinstance(model_data, dict):
                poc_weight = model_data.get("poc_weight")
                if poc_weight is not None:
                    NODE_POC_WEIGHT.labels(
                        node_id=node_id,
                        host=node_host,
                        model=model
                    ).set(poc_weight)
        
        # GPU stats
        if node_port and node_host:
            gpu_count, gpu_avg_util = fetch_gpu_stats(node_host, node_port)
            NODE_GPU_DEVICE_COUNT.labels(node_id=node_id, host=node_host).set(gpu_count)
            NODE_GPU_AVG_UTILIZATION.labels(node_id=node_id, host=node_host).set(gpu_avg_util)


def update_metrics():
    """
    Main metrics update function.
    Calls all sub-update functions based on configuration.
    """
    print(f"[INFO] Updating metrics... (Network={EXPORT_NETWORK_METRICS}, Nodes={ENABLE_NODE_FETCH}, Participant={bool(PARTICIPANT_ADDRESS)})")
    
    # Always update basic Tendermint metrics (backward compatible)
    # When EXPORT_NETWORK_METRICS=true, checks 3 nodes for max block height
    update_tendermint_metrics()
    
    # Conditionally update network-wide metrics (always uses localhost:8000)
    if EXPORT_NETWORK_METRICS:
        update_network_metrics()
        update_pricing_metrics()
        update_model_metrics()
    
    # Update participant stats if address provided (uses localhost:8000)
    update_participant_metrics()
    
    # Update local node metrics
    update_node_metrics()

# =============================================================================
# MAIN
# =============================================================================

def main():
    """
    Start the Prometheus HTTP server and periodically refresh metrics.
    """
    print("=" * 70)
    print("Gonka Prometheus Exporter")
    print("=" * 70)
    print(f"Configuration:")
    print(f"  BASE_URL (local Tendermint): {BASE_URL}")
    print(f"  NETWORK_API_URL (network data): {NETWORK_API_URL}")
    print(f"  NODE_BASE_URL (admin API): {NODE_BASE_URL}")
    print(f"  EXPORTER_PORT: {EXPORTER_PORT}")
    print(f"  REFRESH_INTERVAL: {REFRESH_INTERVAL}s")
    print(f"  EXPORT_NETWORK_METRICS: {EXPORT_NETWORK_METRICS}")
    if EXPORT_NETWORK_METRICS:
        print(f"  BLOCK_HEIGHT_NODES: {', '.join(BLOCK_HEIGHT_NODES)}")
    print(f"  ENABLE_NODE_FETCH: {ENABLE_NODE_FETCH}")
    print(f"  PARTICIPANT_ADDRESS: {'<set>' if PARTICIPANT_ADDRESS else '<not set>'}")
    print("=" * 70)
    
    # Start Prometheus HTTP server
    start_http_server(EXPORTER_PORT)
    print(f"[INFO] Prometheus metrics server started on port {EXPORTER_PORT}")
    print(f"[INFO] Metrics available at http://localhost:{EXPORTER_PORT}/metrics")
    print()
    
    # Initial metrics update
    update_metrics()
    
    # Periodic refresh loop
    while True:
        time.sleep(REFRESH_INTERVAL)
        update_metrics()


if __name__ == "__main__":
    main()
