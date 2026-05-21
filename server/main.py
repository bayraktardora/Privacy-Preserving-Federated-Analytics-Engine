import asyncio
import time
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from models import NodeRegistration, PrivacySummary, GlobalResult
from node_registry import NodeRegistry
from analytics_server import AnalyticsServer
import uvicorn

# ── Singletons ────────────────────────────────────────────────────────────────
server   = AnalyticsServer()
registry = NodeRegistry()

# ── Scheduler config ──────────────────────────────────────────────────────────
AGGREGATE_INTERVAL = int(os.getenv("AGGREGATE_INTERVAL", "15"))   # seconds
_next_aggregate_ts = None   # unix ts of the next scheduled run (for dashboard countdown)


async def _aggregation_loop():
    """
    Background task: every AGGREGATE_INTERVAL seconds, run FedAvg —
    but only if at least one ALIVE node has submitted (avoid empty rounds).
    """
    global _next_aggregate_ts
    while True:
        _next_aggregate_ts = time.time() + AGGREGATE_INTERVAL
        await asyncio.sleep(AGGREGATE_INTERVAL)
        try:
            alive = server.monitor.alive_nodes(registry)
            has_alive_submission = any(nid in registry.submissions for nid in alive)
            if has_alive_submission:
                # federated_average does blocking file I/O → run off the event loop
                result = await asyncio.to_thread(server.federated_average, registry)
                print(f"[scheduler] auto round {result.get('round')} → {result.get('aggregated_value')}")
            else:
                print("[scheduler] skipped — no alive node has submitted")
        except Exception as e:
            print(f"[scheduler] error: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_aggregation_loop())
    print(f"[scheduler] auto-aggregation enabled every {AGGREGATE_INTERVAL}s")
    yield
    task.cancel()


app = FastAPI(
    title="Privacy-Preserving Federated Analytics Engine",
    description="Distributed analytics with differential privacy",
    version="0.4.0",
    lifespan=lifespan,
)


@app.post("/nodes/register")
def register_node(node: NodeRegistration):
    return registry.register(node)


@app.post("/nodes/heartbeat")
def heartbeat(node_id: str):
    result = registry.heartbeat(node_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    # Forward to NodeMonitor so timestamp-based liveness tracking works
    server.record_heartbeat(node_id)
    return result


@app.post("/nodes/submit")
def submit(node_id: str, payload: PrivacySummary):
    result = registry.submit(node_id, payload.model_dump())
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/results")
def get_results():
    return registry.get_results()


@app.post("/aggregate")
def aggregate():
    """Manual trigger — kept for testing alongside the auto-scheduler."""
    result = server.federated_average(registry)
    return result


@app.get("/history")
def get_history():
    return server.get_history()


@app.get("/nodes/status")
def node_status():
    return server.get_node_status(registry)


@app.get("/health")
def health():
    next_in = None
    if _next_aggregate_ts is not None:
        next_in = max(0.0, _next_aggregate_ts - time.time())
    return {
        "status":              "ok",
        "round":               server.round,
        "aggregate_interval":  AGGREGATE_INTERVAL,
        "next_aggregation_in": round(next_in, 1) if next_in is not None else None,
    }


@app.get("/reports")
def reports():
    """Return paths (and content) of the persisted Global Trend Reports."""
    paths = server.get_report_paths()
    result = {"paths": paths}
    # Include JSON report inline if it exists
    try:
        import json
        with open(paths["json"]) as f:
            result["data"] = json.load(f)
    except Exception:
        result["data"] = []
    return result


@app.get("/reports/download/json")
def download_json():
    path = server.get_report_paths()["json"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, media_type="application/json", filename="global_trend_report.json")


@app.get("/reports/download/csv")
def download_csv():
    path = server.get_report_paths()["csv"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not generated yet")
    return FileResponse(path, media_type="text/csv", filename="global_trend_report.csv")


if __name__ == "__main__":
    port = int(os.getenv("SERVER_PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)