"""
analytics_server.py  —  Issue #6: FedAvg Aggregation + Node Monitoring
========================================================================
Implements:
  - IAggregator interface          (combine(summaries) -> GlobalResult)
  - FedAvgAggregator               (weighted average by data_size)
  - AggregatorFactory              (Factory pattern)
  - INodeObserver interface        (on_node_offline / on_round_complete)
  - NodeMonitor                    (Observer pattern, 30-second timeout)
  - AnalyticsServer (Singleton)    (orchestrates everything)
  - Global Trend Report            (written to disk as JSON + CSV)
"""

import csv
import json
import os
import time
from abc import ABC, abstractmethod
from typing import Optional

from node_registry import NodeRegistry

# ── Report output directory ────────────────────────────────────────────────
REPORT_DIR = os.getenv("REPORT_DIR", "/tmp/reports")
os.makedirs(REPORT_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════════════
# IAggregator  —  interface
# ══════════════════════════════════════════════════════════════════════════════

class IAggregator(ABC):
    """
    Abstract aggregator interface.
    combine(summaries) must return a GlobalResult-compatible dict.
    """

    @abstractmethod
    def combine(self, summaries: dict, round_number: int) -> dict:
        """
        Parameters
        ----------
        summaries    : {node_id: payload_dict} — only ALIVE nodes
        round_number : current federation round

        Returns
        -------
        dict matching GlobalResult schema
        """


# ══════════════════════════════════════════════════════════════════════════════
# FedAvgAggregator
# ══════════════════════════════════════════════════════════════════════════════

class FedAvgAggregator(IAggregator):
    """
    Weighted average (FedAvg).
    Each node is weighted by its data_size so larger datasets
    contribute proportionally more — the canonical FedAvg rule.

    Uses noisy_mean when available; falls back to epsilon as a proxy.
    """

    def combine(self, summaries: dict, round_number: int) -> dict:
        if not summaries:
            return {"error": "No active submissions"}

        total_weight = 0.0
        weighted_sum = 0.0

        for node_id, payload in summaries.items():
            data_size  = payload.get("data_size", 1)
            # prefer the real noisy mean; fall back to epsilon proxy
            value      = payload.get("noisy_mean") or payload.get("epsilon", 0.0)
            weighted_sum  += value * data_size
            total_weight  += data_size

        aggregated = weighted_sum / total_weight if total_weight else 0.0

        return {
            "round":               round_number,
            "aggregated_value":    round(aggregated, 6),
            "participating_nodes": list(summaries.keys()),
            "total_data_points":   int(total_weight),
        }


# ══════════════════════════════════════════════════════════════════════════════
# WeightedMeanAggregator  (simple unweighted mean — alternative strategy)
# ══════════════════════════════════════════════════════════════════════════════

class WeightedMeanAggregator(IAggregator):
    """Simple unweighted mean across all node values."""

    def combine(self, summaries: dict, round_number: int) -> dict:
        if not summaries:
            return {"error": "No active submissions"}

        values = [
            p.get("noisy_mean") or p.get("epsilon", 0.0)
            for p in summaries.values()
        ]
        aggregated = sum(values) / len(values)

        return {
            "round":               round_number,
            "aggregated_value":    round(aggregated, 6),
            "participating_nodes": list(summaries.keys()),
            "total_data_points":   sum(p.get("data_size", 1) for p in summaries.values()),
        }


# ══════════════════════════════════════════════════════════════════════════════
# AggregatorFactory  —  Factory pattern
# ══════════════════════════════════════════════════════════════════════════════

class AggregatorFactory:
    """
    Factory for aggregation strategies.

    Usage
    -----
    agg = AggregatorFactory.create_aggregator("fedavg")
    agg = AggregatorFactory.create_aggregator("weighted_mean")
    """

    _registry = {
        "fedavg":        FedAvgAggregator,
        "weighted_mean": WeightedMeanAggregator,
    }

    @classmethod
    def create_aggregator(cls, agg_type: str = "fedavg") -> IAggregator:
        klass = cls._registry.get(agg_type.lower())
        if klass is None:
            raise ValueError(
                f"Unknown aggregator '{agg_type}'. "
                f"Available: {list(cls._registry.keys())}"
            )
        return klass()

    @classmethod
    def register(cls, name: str, klass: type):
        """Allow external code to register custom aggregators."""
        cls._registry[name] = klass


# ══════════════════════════════════════════════════════════════════════════════
# INodeObserver  —  interface
# ══════════════════════════════════════════════════════════════════════════════

class INodeObserver(ABC):
    """Observer interface for node lifecycle events."""

    @abstractmethod
    def on_node_offline(self, node_id: str):
        """Called when a node times out (no heartbeat in 30 s)."""

    @abstractmethod
    def on_round_complete(self, result: dict):
        """Called after each successful aggregation round."""


# ══════════════════════════════════════════════════════════════════════════════
# NodeMonitor  —  Observer pattern
# ══════════════════════════════════════════════════════════════════════════════

HEARTBEAT_TIMEOUT = int(os.getenv("HEARTBEAT_TIMEOUT", "30"))   # seconds


class NodeMonitor(INodeObserver):
    """
    Monitors node liveness using last-heartbeat timestamps.

    A node is considered OFFLINE when:
        now - last_heartbeat_time > HEARTBEAT_TIMEOUT (default 30 s)

    Offline nodes are excluded from FedAvg calculation (fault tolerance).
    """

    def __init__(self):
        # node_id -> unix timestamp of last heartbeat
        self._last_seen: dict[str, float] = {}

    # ── INodeObserver ──────────────────────────────────────────────────────

    def on_node_offline(self, node_id: str):
        print(f"[NodeMonitor] Node '{node_id}' marked OFFLINE (no heartbeat for {HEARTBEAT_TIMEOUT}s)")

    def on_round_complete(self, result: dict):
        print(f"[NodeMonitor] Round {result.get('round')} complete — "
              f"nodes: {result.get('participating_nodes')}, "
              f"value: {result.get('aggregated_value')}")

    # ── Public API ─────────────────────────────────────────────────────────

    def record_heartbeat(self, node_id: str):
        """Call this whenever a /nodes/heartbeat arrives."""
        self._last_seen[node_id] = time.time()

    def is_alive(self, node_id: str) -> bool:
        """Returns True if node sent a heartbeat within the timeout window."""
        last = self._last_seen.get(node_id)
        if last is None:
            return False
        return (time.time() - last) <= HEARTBEAT_TIMEOUT

    def alive_nodes(self, registry: NodeRegistry) -> set[str]:
        """Returns the set of node IDs that are currently alive."""
        return {
            node_id
            for node_id in registry.nodes
            if self.is_alive(node_id)
        }

    def check_and_notify(self, registry: NodeRegistry):
        """
        Scan all registered nodes.
        Fire on_node_offline for any that have timed out.
        """
        for node_id in list(registry.nodes.keys()):
            if not self.is_alive(node_id):
                self.on_node_offline(node_id)


# ══════════════════════════════════════════════════════════════════════════════
# TrendReporter  —  writes Global Trend Reports to disk
# ══════════════════════════════════════════════════════════════════════════════

class TrendReporter:
    """Persists the aggregation history to JSON and CSV files."""

    JSON_PATH = os.path.join(REPORT_DIR, "global_trend_report.json")
    CSV_PATH  = os.path.join(REPORT_DIR, "global_trend_report.csv")

    CSV_FIELDS = ["round", "aggregated_value", "participating_nodes", "total_data_points"]

    @classmethod
    def write(cls, history: list[dict]):
        """Write full history to both JSON and CSV."""
        cls._write_json(history)
        cls._write_csv(history)

    @classmethod
    def _write_json(cls, history: list[dict]):
        with open(cls.JSON_PATH, "w") as f:
            json.dump(history, f, indent=2)

    @classmethod
    def _write_csv(cls, history: list[dict]):
        with open(cls.CSV_PATH, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cls.CSV_FIELDS, extrasaction="ignore")
            writer.writeheader()
            for row in history:
                # serialize list -> comma-separated string for CSV
                row_copy = dict(row)
                if isinstance(row_copy.get("participating_nodes"), list):
                    row_copy["participating_nodes"] = ",".join(row_copy["participating_nodes"])
                writer.writerow(row_copy)


# ══════════════════════════════════════════════════════════════════════════════
# AnalyticsServer  —  Singleton, orchestrates everything
# ══════════════════════════════════════════════════════════════════════════════

class AnalyticsServer:
    """
    Singleton analytics server.

    Responsibilities
    ----------------
    - Aggregate noisy submissions from ALIVE nodes via IAggregator
    - Monitor node liveness through NodeMonitor (Observer pattern)
    - Track federation rounds and persist Global Trend Reports
    """

    _instance: Optional["AnalyticsServer"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "initialized"):
            self.initialized  = True
            self.round        = 0
            self.history:     list[dict] = []
            self.aggregator:  IAggregator = AggregatorFactory.create_aggregator("fedavg")
            self.monitor:     NodeMonitor = NodeMonitor()
            print("AnalyticsServer initialized (Singleton)")

    # ── FedAvg Aggregation ────────────────────────────────────────────────

    def federated_average(self, registry: NodeRegistry) -> dict:
        """
        Compute FedAvg over ALIVE node submissions only.
        Offline nodes (no heartbeat in 30 s) are excluded — fault tolerance.
        """
        # 1. Check for timeouts and notify observers
        self.monitor.check_and_notify(registry)

        # 2. Filter submissions: only alive nodes
        alive = self.monitor.alive_nodes(registry)
        active_submissions = {
            node_id: payload
            for node_id, payload in registry.submissions.items()
            if node_id in alive
        }

        if not active_submissions:
            # Fallback: use all submissions if no alive nodes detected
            # (happens when clients finish and stop heartbeating before aggregate is called)
            active_submissions = registry.submissions

        # 3. Aggregate
        self.round += 1
        result = self.aggregator.combine(active_submissions, self.round)

        # 4. Persist
        self.history.append(result)
        TrendReporter.write(self.history)

        # 5. Notify observer
        self.monitor.on_round_complete(result)

        return result

    # ── NodeMonitor integration ───────────────────────────────────────────

    def record_heartbeat(self, node_id: str):
        """Forward heartbeat timestamp to NodeMonitor."""
        self.monitor.record_heartbeat(node_id)

    def get_node_status(self, registry: NodeRegistry) -> dict:
        """Returns live/dead status using NodeMonitor's timestamp logic."""
        status = {}
        for node_id in registry.nodes:
            status[node_id] = "alive" if self.monitor.is_alive(node_id) else "unreachable"
        return status

    def mark_all_stale(self, registry: NodeRegistry):
        """
        Reset all heartbeat flags (legacy compatibility).
        NodeMonitor uses timestamps so this is a no-op — kept for API stability.
        """
        pass

    # ── History & Reports ─────────────────────────────────────────────────

    def get_history(self) -> list[dict]:
        """Return all past aggregation rounds."""
        return self.history

    def get_report_paths(self) -> dict:
        """Return file paths for the persisted trend reports."""
        return {
            "json": TrendReporter.JSON_PATH,
            "csv":  TrendReporter.CSV_PATH,
        }
