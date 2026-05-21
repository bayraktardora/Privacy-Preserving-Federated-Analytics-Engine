import os
import csv
import json
import random
import numpy as np
import time
import requests
import threading  # <-- Added for background heartbeat
from privacy_strategies import PrivacyMechanismFactory
import pandas as pd
import warnings
from pandas.errors import EmptyDataError

SERVER_URL = os.getenv("SERVER_URL", "http://server:5000")
NODE_ID    = os.getenv("NODE_ID", "client1")
EPSILON    = float(os.getenv("EPSILON", "0.1"))
STRATEGY   = os.getenv("PRIVACY_STRATEGY", "laplace")

# Fetch missing value strategy via environment variable: "drop" or "fill_mean"
MISSING_VALUE_STRATEGY = os.getenv("MISSING_VALUE_STRATEGY", "drop").lower()

# New Interval Controls
SUBMIT_INTERVAL    = int(os.getenv("SUBMIT_INTERVAL", "30"))
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "10"))

class DataLoader:
    """Reads a single-column CSV using Pandas. Falls back to synthetic data if file missing."""
    def __init__(self, filepath: str = "data.csv"):
        self.filepath = filepath

    def load(self) -> np.ndarray:
        # Case: No File -> Keep Fallback
        if not os.path.exists(self.filepath):
            print(f"[{NODE_ID}] '{self.filepath}' not found — using synthetic data")
            return np.array([random.uniform(10, 100) for _ in range(20)])
            
        try:
            # Read CSV
            df = pd.read_csv(self.filepath)
            
            # Case: CSV has headers but no data
            if df.empty:
                warnings.warn(f"[{NODE_ID}] '{self.filepath}' is empty.", UserWarning)
                return np.array([])
                
        except EmptyDataError:
            # Case: CSV is a literally 0-byte blank file
            warnings.warn(f"[{NODE_ID}] '{self.filepath}' is empty.", UserWarning)
            return np.array([])
        except Exception as e:
            # Catch structural breakdown failures
            warnings.warn(f"[{NODE_ID}] Failed parsing '{self.filepath}': {str(e)}", UserWarning)
            return np.array([])

        # Grab the first column series
        series = df.iloc[:, 0]
        
        # Convert contents to numeric data types, turning errors (strings/garbage) into NaN
        series = pd.to_numeric(series, errors='coerce')
        
        # Fetch missing value strategy dynamically at runtime so test mocking works
        strategy = os.getenv("MISSING_VALUE_STRATEGY", "drop").lower()
        
        # Handle Missing Value Strategies
        if strategy == "fill_mean":
            mean_val = series.mean()
            # If the entire column is NaN, mean will be NaN; fallback to filling with 0.0
            if pd.isna(mean_val):
                mean_val = 0.0
            series = series.fillna(mean_val)
        else:
            # Default behavior: "drop"
            series = series.dropna()
            
        print(f"[{NODE_ID}] Loaded {len(series)} rows from '{self.filepath}' using Pandas ({strategy} strategy)")
        return series.to_numpy()


class FeatureExtractor:
    """Computes mean, std and count from NumPy arrays safely using NumPy utilities."""
    def __init__(self, values: np.ndarray):
        self.values = values

    def extract(self) -> dict:
        count = len(self.values)
        if count == 0:
            return {"mean": 0.0, "std": 0.0, "count": 0}
            
        mean = float(np.mean(self.values))
        # ddof=1 replicates standard sample standard deviation (stdev)
        std = float(np.std(self.values, ddof=1)) if count > 1 else 0.0
        return {"mean": mean, "std": std, "count": count}


class NoiseApplicator:
    """Applies the selected privacy mechanism to raw value arrays using vectorized logic."""
    def __init__(self, strategy_name: str, epsilon: float):
        self.mechanism = PrivacyMechanismFactory.create(strategy_name, epsilon=epsilon)

    def apply(self, values: np.ndarray) -> np.ndarray:
        noisy = self.mechanism.apply_noise(values, sensitivity=1.0)
        print(f"[{NODE_ID}] {self.mechanism} applied via NumPy vectors")
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
            "noisy_mean": round(features["mean"], 6),   # <-- used for FedAvg
            "noisy_std":  round(features["std"], 6), 
        }
        print(f"[{NODE_ID}] Payload: {json.dumps(payload)}")
        return payload


class ClientNode:
    """Orchestrates: collectLocalData() -> processAndSend()"""
    def __init__(self):
        self.loader     = DataLoader("data.csv")
        self.noise      = NoiseApplicator(STRATEGY, EPSILON)
        self.serializer = PayloadSerializer(NODE_ID, EPSILON)
        self.running    = True # <-- Added for thread control

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

    def _heartbeat_loop(self):
        """Dedicated background thread for continuous heartbeats."""
        while self.running:
            try:
                r = requests.post(f"{SERVER_URL}/nodes/heartbeat", params={"node_id": NODE_ID}, timeout=2)
                r.raise_for_status()
            except Exception as e:
                print(f"[{NODE_ID}] Heartbeat failed: {e}")
            time.sleep(HEARTBEAT_INTERVAL)

    def _submit(self, payload: dict):
        try:
            r = requests.post(f"{SERVER_URL}/nodes/submit",
                              params={"node_id": NODE_ID}, json=payload, timeout=2)
            r.raise_for_status()
            print(f"[{NODE_ID}] Submitted: {r.json()}")
        except Exception as e:
            print(f"[{NODE_ID}] Submit failed: {e}")

    def collectLocalData(self) -> np.ndarray:
        return self.loader.load()

    def processAndSend(self, raw_data: np.ndarray):
        noisy_data = self.noise.apply(raw_data)
        features   = FeatureExtractor(noisy_data).extract()
        payload    = self.serializer.serialize(features)
        
        # self._heartbeat() <-- Removed, handled by background thread now
        self._submit(payload)

    def run(self):
        self._wait_for_server()
        self._register()

        # Spin up the heartbeat daemon
        hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        hb_thread.start()
        print(f"[{NODE_ID}] Heartbeat thread started. Pinging every {HEARTBEAT_INTERVAL}s.")

        # Enter the continuous submission loop
        print(f"[{NODE_ID}] Entering continuous submission loop (interval: {SUBMIT_INTERVAL}s).")
        while True:
            raw_data = self.collectLocalData()
            self.processAndSend(raw_data)
            time.sleep(SUBMIT_INTERVAL)


if __name__ == "__main__":
    ClientNode().run()