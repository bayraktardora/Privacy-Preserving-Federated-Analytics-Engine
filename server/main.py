from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from models import NodeRegistration, PrivacySummary, GlobalResult
from node_registry import NodeRegistry
from analytics_server import AnalyticsServer
import uvicorn
import os

app = FastAPI(
    title="Privacy-Preserving Federated Analytics Engine",
    description="Distributed analytics with differential privacy",
    version="0.3.0",
)

server   = AnalyticsServer()
registry = NodeRegistry()


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
    result = registry.submit(node_id, payload.dict())
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@app.get("/results")
def get_results():
    return registry.get_results()


@app.post("/aggregate")
def aggregate():
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
    return {"status": "ok", "round": server.round}


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
