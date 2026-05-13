from pydantic import BaseModel
from typing import Optional

class NodeRegistration(BaseModel):
    node_id: str
    address: str
    port: int

class PrivacySummary(BaseModel):
    node_id: str
    epsilon: float
    data_size: int

class GlobalResult(BaseModel):
    round: int
    aggregated_value: float
    participating_nodes: list[str]