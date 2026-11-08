from __future__ import annotations

from pydantic import BaseModel, Field


class TelemetryOutputDirective(BaseModel):
    human_name: str
    value: float | int | bool
    label: str


class TelemetryEvaluationResult(BaseModel):
    latency_us: float
    outputs: dict[str, TelemetryOutputDirective] = Field(default_factory=dict)
    elevated_lineage_nodes: list[str] = Field(default_factory=list)
    full_state: dict[str, float | int | bool] = Field(default_factory=dict)


class EvaluateTelemetryRequest(BaseModel):
    telemetry: dict[str, float | int | bool | str] = Field(default_factory=dict)
