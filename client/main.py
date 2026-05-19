import os
import csv
import json
import random
import statistics
import time
import requests
from privacy_strategies import PrivacyStrategyFactory


SERVER_URL = os.getenv("SERVER_URL", "http://server:5000")
NODE_ID    = os.getenv("NODE_ID", "client1")
EPSILON    = float(os.getenv("EPSILON", "0.1"))
STRATEGY   = os.getenv("PRIVACY_STRATEGY", "laplace")


class DataLoader:
    """Reads a single-column CSV. Falls back to synthetic data if file missing."""
    def __init__(self, filepath: str = "data.csv"):
        self.filepath = filepath

    def load(self) -> list:
        if not os.path.exists(self.filepath):
            print(f"[{NODE_ID}] '{self.filepath}' not found — using synthetic data")
            return [random.uniform(10, 100) for _ in range(20)]
        values = []
        with open(self.filepath, newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row:
                    try:
                        values.append(float(row[0]))
                    except ValueError:
                        pass
        print(f"[{NODE_ID}] Loaded {len(values)} rows from '{self.filepath}'")
        return values


class FeatureExtractor:
    """Computes mean, std and count from raw values."""
    def __init__(self, values: list):
        self.values = values

    def extract(self) -> dict:
        count = len(self.values)
        mean  = statistics.mean(self.values)
        std   = statistics.stdev(self.values) if count > 1 else 0.0
        return {"mean": mean, "std": std, "count": count}


class NoiseApplicator:
    """Applies the selected privacy strategy to raw values."""
    def __init__(self, strategy_name: str, epsilon: float):
        self.strategy = PrivacyStrategyFactory.create(strategy_name, epsilon=epsilon)

    def apply(self, values: list) -> list:
        noisy = self.strategy.apply_batch(values, sensitivity=1.0)
        print(f"[{NODE_ID}] {self.strategy} applied")
        return noisy


class PayloadSerializer:
    """Serializes node results to a JSON-compatible dict."""
    def __init__(self, node_id: str, epsilon: float):
        self.node_id = node_id
        self.epsilon = epsilon

    def serialize(self, features: dict) -> dict:
        payload = {
            "node_id":    self.node_id,
            "epsilon":    self.epsilon,
            "data_size":  features["count"],
            "noisy_mean": round(features["mean"], 6),   # <-- for FedAvg
        }
        print(f"[{NODE_ID}] Payload: {json.dumps(payload)}")
        return payload


class ClientNode:
    """Orchestrates: collectLocalData() -> processAndSend()"""
    def __init__(self):
        self.loader     = DataLoader("data.csv")
        self.noise      = NoiseApplicator(STRATEGY, EPSILON)
        self.serializer = PayloadSerializer(NODE_ID, EPSILON)

    def _wait_for_server(self, retries: int = 10, delay: int = 3):
        for i in range(retries):
            try:
                r = requests.get(f"{SERVER_URL}/health", timeout=2)
                if r.status_code == 200:
                    print(f"[{NODE_ID}] Server is ready.")
                    return
            except Exception:
                pass
            print(f"[{NODE_ID}] Waiting for server... ({i+1}/{retries})")
            time.sleep(delay)
        raise RuntimeError(f"[{NODE_ID}] Server did not become ready.")

    def _register(self):
        r = requests.post(f"{SERVER_URL}/nodes/register",
                          json={"node_id": NODE_ID, "address": NODE_ID, "port": 5000})
        r.raise_for_status()
        print(f"[{NODE_ID}] Registered: {r.json()}")

    def _heartbeat(self):
        r = requests.post(f"{SERVER_URL}/nodes/heartbeat", params={"node_id": NODE_ID})
        r.raise_for_status()
        print(f"[{NODE_ID}] Heartbeat: {r.json()}")

    def _submit(self, payload: dict):
        r = requests.post(f"{SERVER_URL}/nodes/submit",
                          params={"node_id": NODE_ID}, json=payload)
        r.raise_for_status()
        print(f"[{NODE_ID}] Submitted: {r.json()}")

    def collectLocalData(self) -> list:
        return self.loader.load()

    def processAndSend(self, raw_data: list):
        noisy_data = self.noise.apply(raw_data)
        features   = FeatureExtractor(noisy_data).extract()
        payload    = self.serializer.serialize(features)
        self._heartbeat()
        self._submit(payload)

    def run(self):
        self._wait_for_server()
        self._register()
        raw_data = self.collectLocalData()
        self.processAndSend(raw_data)
        print(f"[{NODE_ID}] Pipeline complete.")


if __name__ == "__main__":
    ClientNode().run()
