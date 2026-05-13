from typing import Dict
from models import NodeRegistration

class NodeRegistry:
    def __init__(self):
        self.nodes: Dict[str, NodeRegistration] = {}
        self.heartbeats: Dict[str, bool] = {}
        self.submissions: Dict[str, dict] = {}

    def register(self, node: NodeRegistration):
        self.nodes[node.node_id] = node
        self.heartbeats[node.node_id] = True
        return {"status": "registered", "node_id": node.node_id}

    def heartbeat(self, node_id: str):
        if node_id not in self.nodes:
            return {"status": "error", "message": "Node not found"}
        self.heartbeats[node_id] = True
        return {"status": "alive", "node_id": node_id}

    def submit(self, node_id: str, payload: dict):
        if node_id not in self.nodes:
            return {"status": "error", "message": "Node not found"}
        self.submissions[node_id] = payload
        return {"status": "submitted", "node_id": node_id}

    def get_results(self):
        return {
            "participating_nodes": list(self.nodes.keys()),
            "submissions": self.submissions
        }