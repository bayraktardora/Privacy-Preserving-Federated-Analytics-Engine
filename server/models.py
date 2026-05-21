from pydantic import BaseModel
from typing import Optional


class NodeRegistration(BaseModel):
    """Represents a federated node registering with the server."""

    node_id: str
    address: str
    port: int


class PrivacySummary(BaseModel):
    """Differentially-private summary submitted by a client node."""

    node_id: str
    epsilon: float
    data_size: int
    noisy_mean: Optional[float] = None  # weighted mean used by FedAvg
    noisy_std: Optional[float] = None   # per-node variability indicator


class GlobalResult(BaseModel):
    """Aggregated result produced by the server after one federation round."""

    round: int
    aggregated_value: float
    participating_nodes: list[str]
    total_data_points: int
