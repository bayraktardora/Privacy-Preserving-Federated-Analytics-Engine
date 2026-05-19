from typing import Optional
from node_registry import NodeRegistry


class AnalyticsServer:
    """
    Singleton analytics server.

    Responsibilities:
    - Aggregate noisy submissions from nodes using FedAvg
    - Monitor which nodes are alive (NodeMonitor role)
    - Track federation rounds
    """

    _instance: Optional["AnalyticsServer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized = True
            self.round = 0
            self.history: list[dict] = []
            print("AnalyticsServer initialized (Singleton)")

    # ── FedAvg Aggregation ────────────────────────────────────────────────────

    def federated_average(self, registry: NodeRegistry) -> dict:
        """
        Compute a weighted average (FedAvg) over all node submissions.

        Each node's contribution is weighted by its data_size so larger
        datasets have proportionally more influence — standard FedAvg.

        Returns a GlobalResult-compatible dict.
        """
        submissions = registry.submissions
        if not submissions:
            return {"error": "No submissions yet"}

        total_weight = 0.0
        weighted_sum = 0.0

        for node_id, payload in submissions.items():
            data_size = payload.get("data_size", 1)
            # The client sends epsilon + data_size; noisy mean travels
            # as the "aggregated_value" proxy via data_size weight.
            # Real value: extend PrivacySummary model to include noisy_mean.
            epsilon = payload.get("epsilon", 1.0)
            weighted_sum += epsilon * data_size   # placeholder until noisy_mean added
            total_weight += data_size

        aggregated = weighted_sum / total_weight if total_weight else 0.0
        self.round += 1

        result = {
            "round": self.round,
            "aggregated_value": aggregated,
            "participating_nodes": list(submissions.keys()),
            "total_data_points": int(total_weight),
        }
        self.history.append(result)
        return result

    # ── NodeMonitor ───────────────────────────────────────────────────────────

    def get_node_status(self, registry: NodeRegistry) -> dict:
        """
        Returns live/dead status for every registered node.
        A node is considered alive if it sent a heartbeat.
        """
        status = {}
        for node_id, alive in registry.heartbeats.items():
            status[node_id] = "alive" if alive else "unreachable"
        return status

    def mark_all_stale(self, registry: NodeRegistry):
        """
        Reset all heartbeat flags to False.
        Call this at the start of each round; nodes must re-heartbeat.
        """
        for node_id in registry.heartbeats:
            registry.heartbeats[node_id] = False

    # ── History ───────────────────────────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return all past aggregation rounds."""
        return self.history
