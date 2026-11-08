from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.autoformalisation import AutonomousPolicyGraph
from app.schemas.smt import GraphVerificationReport, TargetConstraintSpec


class SolveForInputsRequest(BaseModel):
    target_constraints: dict[str, TargetConstraintSpec] = Field(default_factory=dict)


class CounterfactualRequest(BaseModel):
    desired_output_var: str
    desired_val: float


class UpdateParamsRequest(BaseModel):
    param_overrides: dict[str, float] = Field(default_factory=dict)


class IngestDocumentRequest(BaseModel):
    raw_text: str
    shuffle_sentences: bool = False


class SystemStateResponse(BaseModel):
    graph: AutonomousPolicyGraph
    param_overrides: dict[str, float] = Field(default_factory=dict)
    verification: GraphVerificationReport
    smtlib2_preview: str = ""
