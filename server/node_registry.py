from typing import Dict
from models import NodeRegistration


class NodeRegistry:
    """In-memory registry that tracks nodes, heartbeat flags and submissions."""

    def __init__(self):
        self.nodes: Dict[str, NodeRegistration] = {}
        self.heartbeats: Dict[str, bool] = {}
        self.submissions: Dict[str, dict] = {}

    def register(self, node: NodeRegistration) -> dict:
        """Register a new node and reset its heartbeat flag.

        Parameters
        ----------
        node : NodeRegistration
            Node metadata (id, address, port).

        Returns
        -------
        dict
            Confirmation with ``status`` and ``node_id`` keys.
        """
        self.nodes[node.node_id] = node
        self.heartbeats[node.node_id] = True
        return {"status": "registered", "node_id": node.node_id}

    def heartbeat(self, node_id: str) -> dict:
        """Record that *node_id* is still alive.

        Parameters
        ----------
        node_id : str
            The ID of the node sending the heartbeat.

        Returns
        -------
        dict
            ``{"status": "alive", "node_id": ...}`` on success, or an error dict
            if the node is not registered.
        """
        if node_id not in self.nodes:
            return {"status": "error", "message": "Node not found"}
        self.heartbeats[node_id] = True
        return {"status": "alive", "node_id": node_id}

    def submit(self, node_id: str, payload: dict) -> dict:
        """Store a differentially-private summary from *node_id*.

        Parameters
        ----------
        node_id : str
            The node submitting data.
        payload : dict
            Privacy summary fields (epsilon, data_size, noisy_mean, …).

        Returns
        -------
        dict
            ``{"status": "submitted", "node_id": ...}`` on success, or an error
            dict if the node is not registered.
        """
        if node_id not in self.nodes:
            return {"status": "error", "message": "Node not found"}
        self.submissions[node_id] = payload
        return {"status": "submitted", "node_id": node_id}

    def get_results(self) -> dict:
        """Return all registered node IDs and their latest submissions.

        Returns
        -------
        dict
            Keys: ``participating_nodes`` (list) and ``submissions`` (dict).
        """
        return {
            "participating_nodes": list(self.nodes.keys()),
            "submissions": self.submissions,
        }
