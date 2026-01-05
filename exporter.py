#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.request
from datetime import datetime

PORT = 9401

def fetch_json(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def get_metrics():
    lines = []
    
    # Block metrics from localhost:26657/status
    status = fetch_json("http://localhost:26657/status")
    if status and "result" in status:
        sync = status["result"].get("sync_info", {})
        height = sync.get("latest_block_height", 0)
        block_time = sync.get("latest_block_time", "")
        
        lines.append(f"# HELP gonka_block_height Latest block height")
        lines.append(f"# TYPE gonka_block_height gauge")
        lines.append(f"gonka_block_height {height}")
        
        if block_time:
            try:
                dt = datetime.fromisoformat(block_time.replace("Z", "+00:00"))
                ts = dt.timestamp()
                lines.append(f"# HELP gonka_block_time_seconds Timestamp of latest block")
                lines.append(f"# TYPE gonka_block_time_seconds gauge")
                lines.append(f"gonka_block_time_seconds {ts}")
            except:
                pass
    
    # ML node metrics from localhost:9200/admin/v1/nodes
    nodes = fetch_json("http://localhost:9200/admin/v1/nodes")
    if nodes and isinstance(nodes, list):
        lines.append(f"# HELP gonka_node_status Node status (0=other, 1=INFERENCE, 2=POC)")
        lines.append(f"# TYPE gonka_node_status gauge")
        lines.append(f"# HELP gonka_node_poc_weight Node POC weight")
        lines.append(f"# TYPE gonka_node_poc_weight gauge")
        
        for item in nodes:
            node = item.get("node", {})
            state = item.get("state", {})
            
            node_id = node.get("id", "unknown")
            host = node.get("host", "unknown")
            current_status = state.get("current_status", "")
            
            # Status values: INFERENCE=1, POC=2, other=0
            if current_status == "INFERENCE":
                status_val = 1
            elif current_status == "POC":
                status_val = 2
            else:
                status_val = 0
            
            # Get model name
            models = list(node.get("models", {}).keys())
            model = models[0] if models else "none"
            
            # Get POC weight
            epoch_ml = state.get("epoch_ml_nodes", {})
            poc_weight = 0
            for m in epoch_ml.values():
                poc_weight = m.get("poc_weight", 0)
                break
            
            labels = f'node_id="{node_id}",host="{host}",model="{model}"'
            lines.append(f"gonka_node_status{{{labels}}} {status_val}")
            lines.append(f"gonka_node_poc_weight{{{labels}}} {poc_weight}")
    
    return "\n".join(lines) + "\n"

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            content = get_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(content.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress logs

if __name__ == "__main__":
    print(f"Gonka exporter running on port {PORT}")
    HTTPServer(("", PORT), Handler).serve_forever()
