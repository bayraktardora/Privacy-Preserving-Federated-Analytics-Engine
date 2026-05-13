from fastapi import FastAPI, HTTPException
from models import NodeRegistration, PrivacySummary, GlobalResult
from node_registry import NodeRegistry
from analytics_server import AnalyticsServer

app = FastAPI()
server = AnalyticsServer()
registry = NodeRegistry()

@app.post("/nodes/register")
def register_node(node: NodeRegistration):
    return registry.register(node)

@app.post("/nodes/heartbeat")
def heartbeat(node_id: str):
    return registry.heartbeat(node_id)

@app.post("/nodes/submit")
def submit(node_id: str, payload: PrivacySummary):
    return registry.submit(node_id, payload.dict())

@app.get("/results")
def get_results():
    return registry.get_results()