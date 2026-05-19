import os
import csv
import time
import requests
from privacy_strategies import PrivacyStrategyFactory


SERVER_URL = os.getenv("SERVER_URL", "http://server:5000")
NODE_ID    = os.getenv("NODE_ID", "client1")
EPSILON    = float(os.getenv("EPSILON", "0.1"))
STRATEGY   = os.getenv("PRIVACY_STRATEGY", "laplace")


def wait_for_server(retries: int = 10, delay: int = 3):
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
    raise RuntimeError(f"[{NODE_ID}] Server did not become ready in time.")


def register():
    payload = {"node_id": NODE_ID, "address": NODE_ID, "port": 5000}
    resp = requests.post(f"{SERVER_URL}/nodes/register", json=payload)
    resp.raise_for_status()
    print(f"[{NODE_ID}] Registered: {resp.json()}")


def load_data(filepath: str = "data.csv") -> list:
    if not os.path.exists(filepath):
        print(f"[{NODE_ID}] No CSV found — using synthetic data")
        import random
        return [random.uniform(10, 100) for _ in range(20)]
    values = []
    with open(filepath, newline="") as f:
        for row in csv.reader(f):
            if row:
                try:
                    values.append(float(row[0]))
                except ValueError:
                    pass
    print(f"[{NODE_ID}] Loaded {len(values)} rows")
    return values


def apply_privacy(values: list) -> tuple:
    strategy = PrivacyStrategyFactory.create(STRATEGY, epsilon=EPSILON)
    noisy_values = strategy.apply_batch(values, sensitivity=1.0)
    noisy_mean = sum(noisy_values) / len(noisy_values)
    print(f"[{NODE_ID}] {strategy}  noisy_mean={noisy_mean:.4f}")
    return noisy_mean, len(values)


def heartbeat():
    resp = requests.post(f"{SERVER_URL}/nodes/heartbeat", params={"node_id": NODE_ID})
    resp.raise_for_status()
    print(f"[{NODE_ID}] Heartbeat: {resp.json()}")


def submit(noisy_mean: float, data_size: int):
    payload = {"node_id": NODE_ID, "epsilon": EPSILON, "data_size": data_size}
    resp = requests.post(f"{SERVER_URL}/nodes/submit", params={"node_id": NODE_ID}, json=payload)
    resp.raise_for_status()
    print(f"[{NODE_ID}] Submitted: {resp.json()}")


if __name__ == "__main__":
    wait_for_server()
    register()
    raw_data = load_data("data.csv")
    noisy_mean, size = apply_privacy(raw_data)
    heartbeat()
    submit(noisy_mean, size)
    print(f"[{NODE_ID}] Pipeline complete.")
