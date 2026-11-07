from typing import Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

ScalarValue = float | int | str | bool | list[str]


class ParameterSpec(BaseModel):
    key: str
    value: float | int | str | bool
    param_type: Literal["real", "int", "string", "bool"]
    description: str
    policy_id: str
    min_bound: float | None = None
    max_bound: float | None = None


class DomainAxiom(BaseModel):
    axiom_id: str
    description: str
    field: str
    min_val: float | None = None
    max_val: float | None = None
    window_accumulates_field: str | None = None


class ComparisonNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_id: str
    node_type: Literal["COMPARISON"] = "COMPARISON"
    policy_id: str
    left_field: str
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "IN"]
    param_ref: str | None = None
    literal_value: ScalarValue | None = None
    right_field: str | None = None
    right_multiplier: float = 1.0


class LogicalGroupNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_id: str
    node_type: Literal["LOGICAL"] = "LOGICAL"
    policy_id: str
    logic_op: Literal["AND", "OR", "NOT"]
    children: list[Union["LogicalGroupNode", ComparisonNode]]


LogicalGroupNode.model_rebuild()


class PolicyItem(BaseModel):
    """Represents a single self-contained, editable policy unit."""

    policy_id: str
    name: str
    enabled: bool = True
    priority: int = 10
    action: Literal["INTERCEPT", "ALLOW_OVERRIDE", "STEP_UP_AUTH"] = "INTERCEPT"
    natural_language_text: str = Field(
        ..., description="Current human-readable policy prose"
    )
    template_text: str = Field(..., description="Prose with {{param_key}} bindings")
    extracted_entities: list[str] = []
    root_node: LogicalGroupNode | ComparisonNode
    cegis_log: list[str] = []


class PolicyDocumentBundle(BaseModel):
    bundle_id: str
    domain_key: str
    title: str
    entity_key: str
    primary_value_field: str
    window_value_field: str
    fields: dict[str, Literal["real", "int", "string", "bool"]]
    axioms: list[DomainAxiom]
    parameters: dict[str, ParameterSpec]
    policies: list[PolicyItem]


class BacktestMetrics(BaseModel):
    sample_size: int
    intercept_count: int
    pass_count: int
    blast_radius_pct: float
    simulated_fraud_recall_pct: float
    false_positive_rate_pct: float
    p50_latency_us: float
    p99_latency_us: float


class UpdateRequestItem(BaseModel):
    """Governance Change Request (In-App PR) tracking policy/parameter edits, Z3 proofs, and metric deltas."""

    request_id: str
    timestamp: str
    author: str
    summary: str
    status: Literal["PENDING_REVIEW", "APPROVED_MERGED", "REJECTED"] = "PENDING_REVIEW"
    candidate_bundle: PolicyDocumentBundle
    nl_diff: list[dict[str, str]]
    z3_report: dict[str, Any]
    metrics_comparison: dict[str, Any]


class RedTeamOccurrence(BaseModel):
    """Tracks red-team or anomalous events that interacted with the data plane and suggests NL patches."""

    occurrence_id: str
    timestamp: str
    source: Literal["Z3_RED_TEAM_SYNTH", "LIVE_ANOMALY_ESCAPEE"]
    event_payload: dict[str, Any]
    decision: str
    triggered_policy: str | None = None
    breach_detected: bool
    suggested_nl_patch: str | None = None
