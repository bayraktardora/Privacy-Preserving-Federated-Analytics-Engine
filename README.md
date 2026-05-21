# Privacy-Preserving Federated Analytics Engine

A distributed analytics system where multiple client nodes compute local statistics, apply **differential privacy noise**, and submit privacy-preserving summaries to a central aggregation server — without sharing raw data.

---

## Architecture

```
┌──────────────┐     register / heartbeat / submit
│  Client Node │ ─────────────────────────────────────┐
│  (client1)   │                                       ▼
├──────────────┤                            ┌──────────────────┐
│  Client Node │ ─────────────────────────► │  Analytics       │
│  (client2)   │    ε-DP noisy summaries     │  Server          │
├──────────────┤                            │  (FedAvg)        │
│  Client Node │ ─────────────────────────► │                  │
│  (client3)   │                            └────────┬─────────┘
└──────────────┘                                     │ aggregated results
                                                     ▼
                                          ┌──────────────────┐
                                          │  Streamlit       │
                                          │  Dashboard       │
                                          └──────────────────┘
```

### Components

| Service | Path | Description |
|---------|------|-------------|
| **server** | `server/` | FastAPI server — node registry, FedAvg aggregation, heartbeat monitoring |
| **client** | `client/` | Python node — loads CSV data, applies DP noise, submits summaries |
| **dashboards** | `dashboards/` | Streamlit dashboard — live node status, trend chart, report downloads |

---

## Setup & Running

### Prerequisites
- Docker ≥ 20.10
- Docker Compose v2

### Start the full pipeline

```bash
# Clone and enter the project
git clone <repo-url>
cd Privacy-Preserving-Federated-Analytics-Engine

# Copy and review environment defaults
cp .env.example .env

# Build and run all services
docker compose up --build
```

This starts:
- `server` on port **5000**
- `dashboard` on port **8080**
- `client1`, `client2`, `client3` — each reading its own CSV file

Open the dashboard at **http://localhost:8080**

### Stop

```bash
docker compose down
```

---

## Configuration

All settings are passed via environment variables (see `docker-compose.yml`):

| Variable | Default | Description |
|----------|---------|-------------|
| `EPSILON` | `0.1` | Differential privacy budget per node |
| `PRIVACY_STRATEGY` | `laplace` | Noise mechanism: `laplace` or `gaussian` |
| `MISSING_VALUE_STRATEGY` | `drop` | How to handle NaN rows: `drop` or `fill_mean` |
| `SUBMIT_INTERVAL` | `30` | Seconds between data submissions |
| `HEARTBEAT_INTERVAL` | `10` | Seconds between heartbeats |
| `AGGREGATE_INTERVAL` | `15` | Server auto-aggregation interval (seconds) |
| `HEARTBEAT_TIMEOUT` | `30` | Seconds before a node is considered offline |
| `EPSILON_BUDGET` | `10.0` | Total ε budget displayed in the dashboard |

---

## Analytics Round (End-to-End Flow)

1. **Register** — each client POSTs to `/nodes/register`
2. **Heartbeat** — a background thread PINGs `/nodes/heartbeat` every 10 s
3. **Submit** — client applies DP noise to local CSV, POSTs noisy summary to `/nodes/submit`
4. **Aggregate** — server auto-runs FedAvg every 15 s (or via `/aggregate` button in dashboard)
5. **Dashboard update** — Streamlit polls `/history`, `/nodes/status`, `/results` and redraws

---

## Privacy Mechanisms

### Laplace Mechanism (`laplace`)
Adds Laplace-distributed noise scaled by `sensitivity / ε`. Provides **ε-DP**.

### Gaussian Mechanism (`gaussian`)
Adds Gaussian noise with `σ = sensitivity · √(2 ln(1.25/δ)) / ε`. Provides **(ε, δ)-DP**.

Epsilon values per node in the default compose file:

| Node | ε | Mechanism |
|------|---|-----------|
| client1 | 0.1 | Laplace (high privacy) |
| client2 | 0.5 | Laplace (medium privacy) |
| client3 | 1.0 | Gaussian (lower privacy) |

---

## Fault Tolerance

The `NodeMonitor` tracks heartbeat timestamps. Any node that has not sent a heartbeat within `HEARTBEAT_TIMEOUT` seconds is excluded from the FedAvg calculation. This means the system continues producing valid aggregations even when nodes drop off.

To test fault tolerance manually:

```bash
# Shut down one node
docker compose stop client2

# Observe the dashboard — client2 turns red and is excluded from aggregation
```

---

## Changing Epsilon

Update `EPSILON` in `docker-compose.yml` for the desired client and restart:

```bash
docker compose up --build client1
```

The dashboard's **Privacy Budget Tracker** will reflect the new value on the next submission round.

---

## Running Unit Tests

Install dependencies (Python 3.11+):

```bash
pip install pytest numpy pandas pydantic fastapi
```

Run all tests:

```bash
# From the project root
pytest server/test_aggregators.py \
       server/test_node_monitor.py \
       client/test_data_loader.py \
       client/test_privacy_strategies.py \
       client/test_payload_serializer.py \
       -v
```

Expected output: **32 passed**.

### Test Coverage

| Module | Test File | What's Tested |
|--------|-----------|---------------|
| `analytics_server.py` | `test_aggregators.py` | FedAvg, WeightedMean, epsilon fallback, empty submissions |
| `analytics_server.py` | `test_node_monitor.py` | Heartbeat liveness, timeout, fault-tolerant FedAvg, Singleton |
| `client/main.py` | `test_data_loader.py` | CSV loading, missing file fallback, NaN strategies |
| `client/main.py` | `test_payload_serializer.py` | FeatureExtractor, PayloadSerializer keys/values/rounding |
| `privacy_strategies.py` | `test_privacy_strategies.py` | Laplace/Gaussian noise, factory, invalid epsilon |

---

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/nodes/register` | Register a new node |
| `POST` | `/nodes/heartbeat?node_id=` | Send a heartbeat |
| `POST` | `/nodes/submit?node_id=` | Submit a privacy summary |
| `GET` | `/nodes/status` | Node liveness status |
| `GET` | `/results` | All submissions |
| `POST` | `/aggregate` | Manually trigger FedAvg |
| `GET` | `/history` | All past aggregation rounds |
| `GET` | `/health` | Server health + next aggregation countdown |
| `GET` | `/reports` | Global trend report (inline JSON) |
| `GET` | `/reports/download/json` | Download JSON report |
| `GET` | `/reports/download/csv` | Download CSV report |

---

## Design Patterns

| Pattern | Where |
|---------|-------|
| **Singleton** | `AnalyticsServer` — single server instance per process |
| **Factory** | `AggregatorFactory`, `PrivacyMechanismFactory` — create strategies by name |
| **Strategy** | `IAggregator`, `IPrivacyMechanism` — swappable algorithms |
| **Observer** | `INodeObserver` / `NodeMonitor` — react to node lifecycle events |

---

## Diagram

```
DataLoader ──► FeatureExtractor ──► NoiseApplicator ──► PayloadSerializer ──► HTTP POST /nodes/submit
                                         │
                               LaplaceStrategy / GaussianStrategy
                               (PrivacyMechanismFactory)

NodeRegistry ◄─── /nodes/register, /nodes/heartbeat, /nodes/submit
     │
     └──► AnalyticsServer (Singleton)
               │
               ├── NodeMonitor (Observer) ── heartbeat timestamps ── fault tolerance
               │
               └── FedAvgAggregator (Strategy) ── weighted average ── GlobalResult
                         │
                         └──► TrendReporter ── /tmp/reports/*.json, *.csv
```
