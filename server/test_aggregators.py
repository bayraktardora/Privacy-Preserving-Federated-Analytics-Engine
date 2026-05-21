import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analytics_server import FedAvgAggregator, WeightedMeanAggregator


# ── FedAvgAggregator ──────────────────────────────────────────────────────

def test_fedavg_uses_zero_not_epsilon():
    """noisy_mean=0.0 must be used as-is, NOT replaced by epsilon (issue #10)."""
    agg = FedAvgAggregator()
    summaries = {
        "client1": {"noisy_mean": 0.0, "epsilon": 0.5, "data_size": 100},
    }
    result = agg.combine(summaries, round_number=1)
    assert result["aggregated_value"] == 0.0, \
        f"Expected 0.0 but got {result['aggregated_value']} (epsilon leaked in)"


def test_fedavg_falls_back_to_epsilon_when_missing():
    """When noisy_mean key is absent, fall back to epsilon."""
    agg = FedAvgAggregator()
    summaries = {
        "client1": {"epsilon": 0.5, "data_size": 100},   # no noisy_mean
    }
    result = agg.combine(summaries, round_number=1)
    assert result["aggregated_value"] == 0.5, \
        f"Expected epsilon fallback 0.5 but got {result['aggregated_value']}"


def test_fedavg_multinode_with_zero_mean():
    """A 0.0-mean node must contribute 0.0, even next to non-zero nodes."""
    agg = FedAvgAggregator()
    summaries = {
        "client1": {"noisy_mean": 0.0,  "epsilon": 0.1, "data_size": 100},
        "client2": {"noisy_mean": 10.0, "epsilon": 0.5, "data_size": 100},
    }
    result = agg.combine(summaries, round_number=1)
    # correct: (0.0*100 + 10.0*100) / 200 = 5.0
    # buggy:   (0.1*100 + 10.0*100) / 200 = 5.05
    assert result["aggregated_value"] == 5.0, \
        f"Expected 5.0 but got {result['aggregated_value']}"


# ── WeightedMeanAggregator ──────────────────────────────────────────────────

def test_weighted_mean_uses_zero_not_epsilon():
    agg = WeightedMeanAggregator()
    summaries = {
        "client1": {"noisy_mean": 0.0, "epsilon": 0.5, "data_size": 100},
    }
    result = agg.combine(summaries, round_number=1)
    assert result["aggregated_value"] == 0.0, \
        f"Expected 0.0 but got {result['aggregated_value']}"


def test_weighted_mean_falls_back_to_epsilon_when_missing():
    agg = WeightedMeanAggregator()
    summaries = {
        "client1": {"epsilon": 0.5, "data_size": 100},
    }
    result = agg.combine(summaries, round_number=1)
    assert result["aggregated_value"] == 0.5, \
        f"Expected epsilon fallback 0.5 but got {result['aggregated_value']}"


# ── Sanity ────────────────────────────────────────────────────────────────

def test_empty_submissions_returns_error():
    agg = FedAvgAggregator()
    result = agg.combine({}, round_number=1)
    assert "error" in result


if __name__ == "__main__":
    test_fedavg_uses_zero_not_epsilon()
    test_fedavg_falls_back_to_epsilon_when_missing()
    test_fedavg_multinode_with_zero_mean()
    test_weighted_mean_uses_zero_not_epsilon()
    test_weighted_mean_falls_back_to_epsilon_when_missing()
    test_empty_submissions_returns_error()
    print("All aggregator tests passed ✅")