from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ScalarValue = float | int | str | bool | list[str]


# =====================================================================
# Domain Enums (StrEnum)
# =====================================================================


class DataType(StrEnum):
    """Primitive data type representation for parameters and policy fields."""

    REAL = "real"
    INT = "int"
    STRING = "string"
    BOOL = "bool"


class NodeType(StrEnum):
    """AST node classification for policy rule graphs."""

    COMPARISON = "COMPARISON"
    LOGICAL = "LOGICAL"


class ComparisonOperator(StrEnum):
    """Relational comparison operators for policy AST nodes."""

    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    IN = "IN"


class LogicalOperator(StrEnum):
    """Boolean logic connectives for policy AST grouping nodes."""

    AND = "AND"
    OR = "OR"
    NOT = "NOT"


class PolicyAction(StrEnum):
    """Enforcement action directives triggered upon policy satisfaction."""

    INTERCEPT = "INTERCEPT"
    ALLOW_OVERRIDE = "ALLOW_OVERRIDE"
    STEP_UP_AUTH = "STEP_UP_AUTH"


class UpdateRequestStatus(StrEnum):
    """Lifecycle status of a governance change request pull request."""

    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED_MERGED = "APPROVED_MERGED"
    REJECTED = "REJECTED"


class RedTeamSource(StrEnum):
    """Source classification for red team anomalous event triggers."""

    Z3_RED_TEAM_SYNTH = "Z3_RED_TEAM_SYNTH"
    LIVE_ANOMALY_ESCAPEE = "LIVE_ANOMALY_ESCAPEE"


class VariableRole(StrEnum):
    """Topological graph-theoretic role of a policy variable."""

    INPUT = "INPUT"
    INTERMEDIATE = "INTERMEDIATE"
    OUTPUT = "OUTPUT"
    PARAMETER = "PARAMETER"


class VariableSort(StrEnum):
    """First-order logic sort representation in Z3 SMT solver."""

    REAL = "real"
    INT = "int"
    BOOL = "bool"


class ConceptModality(StrEnum):
    """Semantic modality classification for variables and concepts."""

    NUMERICAL = "numerical"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"


class ConstraintOperator(StrEnum):
    """Comparison operator applied to target variables during abductive solving."""

    EQ = "=="
    NE = "!="
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="


class AbductiveSolveStatus(StrEnum):
    """Outcome status of abductive backward input synthesis."""

    SATISFIABLE = "SATISFIABLE"
    UNSATISFIABLE = "UNSATISFIABLE"


class CounterfactualStatus(StrEnum):
    """Outcome status of MaxSMT counterfactual minimal repair search."""

    COUNTERFACTUAL_FOUND = "COUNTERFACTUAL_FOUND"
    UNSAT = "UNSAT"


class VerificationStatus(StrEnum):
    """Formal proof outcome for overall policy graph verification."""

    VERIFIED = "VERIFIED"
    DEAD_LOGIC_DETECTED = "DEAD_LOGIC_DETECTED"


# =====================================================================
# Legacy Policy Bundle Contracts
# =====================================================================


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
    """Represents a single self-contained, editable policy unit."""

    policy_id: str
    name: str
    enabled: bool = True
    priority: int = 10
    action: PolicyAction = PolicyAction.INTERCEPT
    natural_language_text: str = Field(
        ..., description="Current human-readable policy prose"
    )
    template_text: str = Field(..., description="Prose with {{param_key}} bindings")
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
    """Governance Change Request (In-App PR) tracking policy/parameter edits, Z3 proofs, and metric deltas."""

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
    """Tracks red-team or anomalous events that interacted with the data plane and suggests NL patches."""

    occurrence_id: str
    timestamp: str
    source: RedTeamSource = RedTeamSource.Z3_RED_TEAM_SYNTH
    event_payload: dict[str, Any] = Field(default_factory=dict)
    decision: str
    triggered_policy: str | None = None
    breach_detected: bool
    suggested_nl_patch: str | None = None


# =====================================================================
# Autonomous DAG Architecture Contracts
# =====================================================================


class InferredVariable(BaseModel):
    """An entity autonomously discovered and resolved across unordered sentences."""

    var_id: str
    human_name: str
    role: VariableRole
    in_degree: int = Field(
        0, description="Number of upstream concepts this variable depends on"
    )
    out_degree: int = Field(
        0, description="Number of downstream concepts that depend on this variable"
    )
    layer_index: int = Field(
        0, description="Topological depth: 0 for deg-(v)==0 inputs, K for sinks"
    )
    sort: VariableSort
    ordinal_levels: dict[int, str] | None = None
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float | int | bool = 0.0
    source_sentence_ids: list[int] = Field(
        default_factory=list,
        description="Sentence indices anywhere in the text that reference/define this entity",
    )
    source_excerpts: list[str] = Field(default_factory=list)


class InferredEquation(BaseModel):
    """A Z3 symbolic equation synthesized by aggregating all sentences governing `target_var`."""

    equation_id: str
    target_var: str
    dependencies: list[str] = Field(default_factory=list)
    smt_expression: str = Field(
        ..., description="Valid Z3 symbolic formula using v['var_id']"
    )
    natural_language_logic: str = ""
    source_sentence_ids: list[int] = Field(default_factory=list)


class AutonomousPolicyGraph(BaseModel):
    graph_id: str
    title: str
    raw_document_text: str
    sentence_count: int
    variables: dict[str, InferredVariable] = Field(default_factory=dict)
    equations: dict[str, InferredEquation] = Field(default_factory=dict)
    topological_order: list[str] = Field(default_factory=list)
    cegis_compiler_log: list[str] = Field(default_factory=list)


# =====================================================================
# Strict Data Contracts for Solver & Runtime Operations
# =====================================================================


class VariableSolvedState(BaseModel):
    """Structured concrete valuation of a variable extracted from a Z3 SAT model."""

    human_name: str
    value: float | int | bool
    formatted: str
    layer: int = 0


class SolvedModelWitness(BaseModel):
    """Separated variable assignments grouped by their topological graph role."""

    INPUT: dict[str, VariableSolvedState] = Field(default_factory=dict)
    INTERMEDIATE: dict[str, VariableSolvedState] = Field(default_factory=dict)
    OUTPUT: dict[str, VariableSolvedState] = Field(default_factory=dict)
    PARAMETER: dict[str, VariableSolvedState] = Field(default_factory=dict)


class TargetConstraintSpec(BaseModel):
    """User-specified constraint applied during abductive input synthesis."""

    op: ConstraintOperator = ConstraintOperator.EQ
    val: float | int | bool | str


class AbductiveSolveResult(BaseModel):
    """Result of solving backwards from target states to primary input variables."""

    status: AbductiveSolveStatus
    applied_targets: list[str] = Field(default_factory=list)
    solved_state: SolvedModelWitness | None = None
    message: str = ""


class ChangedInputSpec(BaseModel):
    """Minimal modification required on a primary input to reach counterfactual goal."""

    human_name: str
    previous_value: float | int | bool
    required_value: str


class CounterfactualResult(BaseModel):
    """Max-SMT optimization result identifying minimal primary input deviations."""

    status: CounterfactualStatus
    minimal_input_changes_count: int = 0
    changed_inputs: dict[str, ChangedInputSpec] = Field(default_factory=dict)
    resulting_outputs: dict[str, VariableSolvedState] = Field(default_factory=dict)
    message: str = ""


class ReachabilityProof(BaseModel):
    """Proof record for an output state reachable under active parameter values."""

    output_var: str
    human_name: str
    target_state: str
    reachable: bool


class GraphVerificationReport(BaseModel):
    """Formal audit report proving base satisfiability and absence of dead states."""

    status: VerificationStatus
    consistent: bool
    dead_state_warnings: list[str] = Field(default_factory=list)
    reachability_proofs: list[ReachabilityProof] = Field(default_factory=list)


class TelemetryOutputDirective(BaseModel):
    """Concrete evaluated output directive state with human-readable label."""

    human_name: str
    value: float | int | bool
    label: str


class TelemetryEvaluationResult(BaseModel):
    """High-frequency evaluation result produced by the topological DAG runtime."""

    latency_us: float
    outputs: dict[str, TelemetryOutputDirective] = Field(default_factory=dict)
    elevated_lineage_nodes: list[str] = Field(default_factory=list)
    full_state: dict[str, float | int | bool] = Field(default_factory=dict)


# =====================================================================
# API Request Contracts
# =====================================================================


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


class EvaluateTelemetryRequest(BaseModel):
    """Custom input telemetry values submitted from the frontend for DAG evaluation."""

    telemetry: dict[str, float | int | bool] = Field(default_factory=dict)


class SystemStateResponse(BaseModel):
    """Full system state response returned by state query and update endpoints."""

    graph: AutonomousPolicyGraph
    param_overrides: dict[str, float] = Field(default_factory=dict)
    verification: GraphVerificationReport
    smtlib2_preview: str = ""
