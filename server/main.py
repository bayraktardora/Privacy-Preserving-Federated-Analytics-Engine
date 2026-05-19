from fastapi import FastAPI, HTTPException
from models import NodeRegistration, PrivacySummary, GlobalResult
from node_registry import NodeRegistry
from analytics_server import AnalyticsServer
import uvicorn
import os

app = FastAPI(
    title="Privacy-Preserving Federated Analytics Engine",
    description="Distributed analytics with differential privacy",
    version="0.2.0",
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
    server.mark_all_stale(registry)
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

if __name__ == "__main__":
    port = int(os.getenv("SERVER_PORT", 5000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)