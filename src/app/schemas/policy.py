from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import (
    ComparisonOperator,
    DataType,
    LogicalOperator,
    NodeType,
    PolicyAction,
    RedTeamSource,
    UpdateRequestStatus,
)

ScalarValue = float | int | str | bool | list[str]


class ParameterSpec(BaseModel):
    key: str
    value: float | int | str | bool
    param_type: DataType = DataType.REAL
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
    node_type: NodeType = NodeType.COMPARISON
    policy_id: str
    left_field: str
    operator: ComparisonOperator = ComparisonOperator.EQ
    param_ref: str | None = None
    literal_value: ScalarValue | None = None
    right_field: str | None = None
    right_multiplier: float = 1.0


class LogicalGroupNode(BaseModel):
    model_config = ConfigDict(extra="ignore")
    node_id: str
    node_type: NodeType = NodeType.LOGICAL
    policy_id: str
    logic_op: LogicalOperator = LogicalOperator.AND
    children: list[LogicalGroupNode | ComparisonNode]


LogicalGroupNode.model_rebuild()


class PolicyItem(BaseModel):
    policy_id: str
    name: str
    enabled: bool = True
    priority: int = 10
    action: PolicyAction = PolicyAction.INTERCEPT
    natural_language_text: str
    template_text: str
    extracted_entities: list[str] = Field(default_factory=list)
    root_node: LogicalGroupNode | ComparisonNode
    cegis_log: list[str] = Field(default_factory=list)


class PolicyDocumentBundle(BaseModel):
    bundle_id: str
    domain_key: str
    title: str
    entity_key: str
    primary_value_field: str
    window_value_field: str
    fields: dict[str, DataType] = Field(default_factory=dict)
    axioms: list[DomainAxiom] = Field(default_factory=list)
    parameters: dict[str, ParameterSpec] = Field(default_factory=dict)
    policies: list[PolicyItem] = Field(default_factory=list)


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
    request_id: str
    timestamp: str
    author: str
    summary: str
    status: UpdateRequestStatus = UpdateRequestStatus.PENDING_REVIEW
    candidate_bundle: PolicyDocumentBundle
    nl_diff: list[dict[str, str]] = Field(default_factory=list)
    z3_report: dict[str, Any] = Field(default_factory=dict)
    metrics_comparison: dict[str, Any] = Field(default_factory=dict)


class RedTeamOccurrence(BaseModel):
    occurrence_id: str
    timestamp: str
    source: RedTeamSource = RedTeamSource.Z3_RED_TEAM_SYNTH
    event_payload: dict[str, Any] = Field(default_factory=dict)
    decision: str
    triggered_policy: str | None = None
    breach_detected: bool
    suggested_nl_patch: str | None = None
