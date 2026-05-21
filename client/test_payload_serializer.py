"""
test_payload_serializer.py — Unit tests for PayloadSerializer and FeatureExtractor
===================================================================================
"""

import sys
import os
import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["NODE_ID"] = "test_node"

from main import PayloadSerializer, FeatureExtractor


# ── FeatureExtractor ────────────────────────────────────────────────────────

def test_feature_extractor_normal():
    """Mean, std and count should be computed correctly for a simple array."""
    values = np.array([10.0, 20.0, 30.0])
    features = FeatureExtractor(values).extract()

    assert features["count"] == 3
    assert abs(features["mean"] - 20.0) < 1e-9
    assert features["std"] > 0.0


def test_feature_extractor_empty():
    """Empty array should return count=0 and zero mean/std without crashing."""
    features = FeatureExtractor(np.array([])).extract()
    assert features["count"] == 0
    assert features["mean"] == 0.0
    assert features["std"] == 0.0


def test_feature_extractor_single_element():
    """Single-element array: std is 0 (no variance), mean equals the element."""
    features = FeatureExtractor(np.array([42.0])).extract()
    assert features["count"] == 1
    assert features["mean"] == 42.0
    assert features["std"] == 0.0


def test_feature_extractor_identical_values():
    """All-identical values should give std=0."""
    values = np.full(10, 5.0)
    features = FeatureExtractor(values).extract()
    assert features["std"] == 0.0
    assert features["mean"] == 5.0


# ── PayloadSerializer ───────────────────────────────────────────────────────

def test_payload_serializer_keys():
    """Serialized payload must contain all required keys."""
    serializer = PayloadSerializer(node_id="node1", epsilon=0.5)
    features = {"mean": 25.0, "std": 3.5, "count": 100}
    payload = serializer.serialize(features)

    for key in ("node_id", "epsilon", "data_size", "noisy_mean", "noisy_std"):
        assert key in payload, f"Missing key: {key}"


def test_payload_serializer_values():
    """Serialized values must match the input features."""
    serializer = PayloadSerializer(node_id="nodeX", epsilon=0.1)
    features = {"mean": 15.0, "std": 2.0, "count": 50}
    payload = serializer.serialize(features)

    assert payload["node_id"] == "nodeX"
    assert payload["epsilon"] == 0.1
    assert payload["data_size"] == 50
    assert payload["noisy_mean"] == 15.0
    assert payload["noisy_std"] == 2.0


def test_payload_serializer_rounds_to_6_decimals():
    """noisy_mean and noisy_std must be rounded to 6 decimal places."""
    serializer = PayloadSerializer(node_id="n", epsilon=1.0)
    # Use a value with many decimal places
    features = {"mean": 1.123456789, "std": 0.987654321, "count": 10}
    payload = serializer.serialize(features)

    # Round to 6 places
    assert payload["noisy_mean"] == round(1.123456789, 6)
    assert payload["noisy_std"] == round(0.987654321, 6)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
