"""
test_node_monitor.py — Unit tests for NodeMonitor and AnalyticsServer
=====================================================================
Covers:
  - NodeMonitor.is_alive / record_heartbeat
  - NodeMonitor.alive_nodes (fault tolerance: dead nodes excluded)
  - AnalyticsServer.federated_average fallback when all nodes stale
  - AnalyticsServer Singleton guarantee
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from analytics_server import NodeMonitor, AnalyticsServer, FedAvgAggregator
from node_registry import NodeRegistry
from models import NodeRegistration


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_registry(*node_ids: str) -> NodeRegistry:
    """Create a NodeRegistry pre-populated with the given node IDs."""
    reg = NodeRegistry()
    for nid in node_ids:
        reg.register(NodeRegistration(node_id=nid, address=nid, port=5000))
    return reg


# ── NodeMonitor: liveness ──────────────────────────────────────────────────

def test_node_alive_after_heartbeat():
    """A node should be alive immediately after a heartbeat."""
    monitor = NodeMonitor()
    monitor.record_heartbeat("client1")
    assert monitor.is_alive("client1"), "Node should be alive right after heartbeat"


def test_node_unknown_is_not_alive():
    """A node that never sent a heartbeat must not be alive."""
    monitor = NodeMonitor()
    assert not monitor.is_alive("ghost_node"), "Unknown node must not be alive"


def test_node_times_out(monkeypatch):
    """A node whose last heartbeat was >TIMEOUT seconds ago is considered offline."""
    import analytics_server as as_mod

    monitor = NodeMonitor()
    # Record heartbeat at a fixed timestamp in the past
    past_ts = time.time() - 60  # 60 s ago
    monitor._last_seen["client1"] = past_ts
    # is_alive uses the real time.time() — no monkeypatching needed
    assert not monitor.is_alive("client1"), "Node should time out after HEARTBEAT_TIMEOUT seconds"


def test_alive_nodes_excludes_dead(monkeypatch):
    """alive_nodes() must return only living nodes."""
    import analytics_server as as_mod

    reg = _make_registry("client1", "client2")
    monitor = NodeMonitor()

    # client1 sent a heartbeat; client2 never did
    monitor.record_heartbeat("client1")

    alive = monitor.alive_nodes(reg)
    assert "client1" in alive, "client1 should be alive"
    assert "client2" not in alive, "client2 never heartbeated — must be excluded"


def test_alive_nodes_all_alive():
    """All nodes should appear when all have recent heartbeats."""
    reg = _make_registry("n1", "n2", "n3")
    monitor = NodeMonitor()
    for nid in ("n1", "n2", "n3"):
        monitor.record_heartbeat(nid)
    assert monitor.alive_nodes(reg) == {"n1", "n2", "n3"}


# ── NodeMonitor: offline notification ─────────────────────────────────────

def test_check_and_notify_fires_for_dead_node(capsys):
    """check_and_notify must log an OFFLINE message for timed-out nodes."""
    import time as _time
    reg = _make_registry("client1")
    monitor = NodeMonitor()
    # Plant a stale timestamp directly (60 s ago)
    monitor._last_seen["client1"] = _time.time() - 60

    monitor.check_and_notify(reg)

    captured = capsys.readouterr()
    assert "OFFLINE" in captured.out or "offline" in captured.out.lower()


# ── AnalyticsServer: Singleton ────────────────────────────────────────────

def test_analytics_server_singleton():
    """AnalyticsServer() must always return the same instance."""
    s1 = AnalyticsServer()
    s2 = AnalyticsServer()
    assert s1 is s2, "AnalyticsServer must be a singleton"


# ── AnalyticsServer: federated_average with fault tolerance ───────────────

def test_federated_average_excludes_offline_node(monkeypatch):
    """Offline nodes must be excluded from FedAvg when alive alternatives exist."""
    import analytics_server as as_mod

    # Reset singleton for a clean round counter
    as_mod.AnalyticsServer._instance = None
    server = as_mod.AnalyticsServer()

    reg = _make_registry("client1", "client2")

    # Only client1 is alive
    server.monitor.record_heartbeat("client1")
    # client2 never heartbeated → excluded

    reg.submit("client1", {"noisy_mean": 10.0, "epsilon": 0.1, "data_size": 100})
    reg.submit("client2", {"noisy_mean": 99.0, "epsilon": 0.1, "data_size": 100})

    result = server.federated_average(reg)

    assert "client2" not in result["participating_nodes"], \
        "Dead client2 must be excluded from FedAvg"
    assert result["aggregated_value"] == 10.0, \
        f"Expected 10.0 (client1 only) but got {result['aggregated_value']}"

    # Cleanup singleton
    as_mod.AnalyticsServer._instance = None


def test_federated_average_fallback_when_no_alive_nodes():
    """When no node is alive, fall back to all submissions."""
    import analytics_server as as_mod

    as_mod.AnalyticsServer._instance = None
    server = as_mod.AnalyticsServer()

    reg = _make_registry("client1")
    reg.submit("client1", {"noisy_mean": 42.0, "epsilon": 0.1, "data_size": 50})
    # No heartbeat recorded → NodeMonitor sees no alive nodes

    result = server.federated_average(reg)

    # Should fall back to using the submission anyway
    assert result["aggregated_value"] == 42.0, \
        f"Fallback should use submission; got {result['aggregated_value']}"

    as_mod.AnalyticsServer._instance = None


def test_node_status_reflects_liveness():
    """get_node_status must return 'alive'/'unreachable' based on heartbeats."""
    import analytics_server as as_mod

    as_mod.AnalyticsServer._instance = None
    server = as_mod.AnalyticsServer()

    reg = _make_registry("n1", "n2")
    server.record_heartbeat("n1")

    status = server.get_node_status(reg)
    assert status["n1"] == "alive"
    assert status["n2"] == "unreachable"

    as_mod.AnalyticsServer._instance = None


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
