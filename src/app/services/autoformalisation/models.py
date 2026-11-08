from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class Modality(StrEnum):
    NUMERICAL = "numerical"
    ORDINAL = "ordinal"
    CATEGORICAL = "categorical"


class Z3SortType(StrEnum):
    REAL = "real"
    INT = "int"


class EntityRole(StrEnum):
    INPUT = "input"
    INTERMEDIATE = "intermediate"
    OUTPUT = "output"


class DiscreteStateMapping(BaseModel):
    """Maps an ordered discrete tier/state to its index and unified risk intensity."""

    state_index: int = Field(
        description="0-based integer index (0 = lowest/nominal, N = highest/critical)"
    )
    state_label: str = Field(description="Exact name of the state or tier from text")
    intensity_score: float = Field(
        description="Mapped intensity on the 0.0 to 100.0 scale"
    )


class NumericalThresholdMapping(BaseModel):
    """Defines how a continuous numerical input maps to 0..100 risk intensity."""

    comparison_op: Literal[">=", ">", "<=", "<", "=="] = Field(
        description="Operator checking if metric breaches its risk threshold"
    )
    threshold_value: float = Field(description="Threshold cutoff number")
    breach_intensity: float = Field(
        description="Risk intensity when threshold holds (typically 100.0)"
    )
    baseline_intensity: float = Field(
        description="Baseline risk intensity when within bounds"
    )
    inverted_vulnerability_intensity: float | None = Field(
        default=None,
        description="Optional inverted vulnerability score when non-breached",
    )


class PolicyEntity(BaseModel):
    """Canonical representation of any variable in the policy document."""

    canonical_id: str = Field(description="snake_case identifier")
    original_name: str = Field(description="Exact human-readable name in text")
    role: EntityRole = Field(description="Entity role: input, intermediate, or output")
    modality: Modality = Field(description="Modality: numerical, ordinal, categorical")
    z3_sort: Z3SortType = Field(description="Z3 sort: real or int")
    min_bound: float = Field(default=0.0, description="Minimum valid value")
    max_bound: float = Field(default=100.0, description="Maximum valid value")
    discrete_states: list[DiscreteStateMapping] = Field(
        default_factory=list, description="Ordered states if ordinal/categorical"
    )
    numerical_mapping: NumericalThresholdMapping | None = Field(
        default=None, description="Threshold mapping if foundational indicator"
    )


class SemanticClause(BaseModel):
    """A self-contained logical statement extracted from raw policy text."""

    clause_id: str = Field(description="Unique identifier like clause_001")
    clause_type: Literal[
        "global_axiom",
        "entity_definition",
        "derivation_rule",
        "global_framework",
        "other",
    ] = Field(description="Category of clause")
    normalized_proposition: str = Field(
        description="Self-contained statement with pronouns resolved"
    )
    source_excerpt: str = Field(description="Verbatim excerpt from raw text")
    mentioned_entity_names: list[str] = Field(
        default_factory=list, description="Entities mentioned in clause"
    )


class ClauseDecompositionBatch(BaseModel):
    clauses: list[SemanticClause] = Field(default_factory=list)


class GlobalPolicyFramework(BaseModel):
    """Captures document-wide calculation framework and scale conventions."""

    scale_min: float = Field(default=0.0)
    scale_max: float = Field(default=100.0)
    inversion_formula_description: str = Field(
        default="100.0 minus current risk intensity"
    )
    simultaneous_and_rule_description: str = Field(default="Lowest active intensity")
    escalation_or_rule_description: str = Field(default="Highest triggered intensity")
    standard_tier_alignments: str = Field(
        default="3-tier: 0/50/100, 4-tier: 0/33.3/66.7/100, 5-tier: 0/25/50/75/100"
    )


class OntologyExtractionResult(BaseModel):
    global_framework: GlobalPolicyFramework
    entities: list[PolicyEntity] = Field(default_factory=list)


class EntityDependencyLink(BaseModel):
    """Maps a derived entity to the clauses and inputs governing its outcome."""

    target_canonical_id: str = Field(description="Canonical ID of target entity")
    governing_clause_ids: list[str] = Field(default_factory=list)
    input_canonical_ids: list[str] = Field(default_factory=list)
    reasoning_summary: str = Field(default="")


class DependencyMappingBatch(BaseModel):
    links: list[EntityDependencyLink] = Field(default_factory=list)


LogicExprKind = Literal[
    "literal_real",
    "literal_int",
    "var_ref",
    "var_intensity",
    "complement_100",
    "compare",
    "and_op",
    "or_op",
    "not_op",
    "ite",
    "min_pool",
    "max_pool",
]


class LogicExpr(BaseModel):
    """Recursive, strongly-typed AST node representing a Z3 expression."""

    kind: LogicExprKind
    float_val: float | None = None
    int_val: int | None = None
    var_id: str | None = None
    invert_intensity: bool = False
    comp_op: Literal["==", "!=", "<", "<=", ">", ">="] | None = None
    left: LogicExpr | None = None
    right: LogicExpr | None = None
    args: list[LogicExpr] | None = None
    cond: LogicExpr | None = None
    then_branch: LogicExpr | None = None
    else_branch: LogicExpr | None = None


LogicExpr.model_rebuild()


class EmpiricalTestCase(BaseModel):
    """Anchor test case extracted from policy prose to verify synthesized rule."""

    description: str
    input_assignments: dict[str, float | int]
    expected_target_value: float | int


class SynthesizedNodeRule(BaseModel):
    """Synthesized AST rule and verification test cases for a single target."""

    target_canonical_id: str
    reasoning_trace: str
    expr_ast: LogicExpr
    continuous_intensity_ast: LogicExpr | None = None
    test_cases: list[EmpiricalTestCase] = Field(default_factory=list)


class RawSentence(BaseModel):
    """Segmented sentence unit with document position index."""

    index: int
    text: str


class ResolvedConcept(BaseModel):
    """Resolved concept specification matching graph variable contract."""

    cid: str
    human_name: str
    sort: str = "real"
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float | int | bool = 0.0
    ordinal_levels: dict[int, str] | None = None
    sentence_ids: list[int] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


class CausalLink(BaseModel):
    """Directed dependency link between target and parent entities."""

    target_id: str
    parent_ids: list[str] = Field(default_factory=list)
    logic_summary: str = ""
    sentence_id: int = 0


class ExtractedEntity(BaseModel):
    """Coerces loose LLM JSON outputs into strict schema."""

    id: str
    human_name: str = ""
    sort: str = "real"
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float | int | bool = 0.0
    ordinal_levels: dict[int, str] | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        res = dict(data)
        if "id" not in res and "cid" in res:
            res["id"] = res["cid"]
        if "human_name" not in res or not res["human_name"]:
            res["human_name"] = str(res.get("id", "")).replace("_", " ").title()
        ord_levels = res.get("ordinal_levels")
        if isinstance(ord_levels, list):
            res["ordinal_levels"] = {i: str(v) for i, v in enumerate(ord_levels)}
            res["sort"] = "int"
            res["min_bound"] = 0.0
            res["max_bound"] = float(len(ord_levels) - 1)
        if res.get("sort") not in ("real", "int", "bool"):
            res["sort"] = "real"
        if res.get("min_bound") is None:
            res["min_bound"] = 0.0
        if res.get("max_bound") is None:
            res["max_bound"] = 100.0
        return res


class SentenceMapResponse(BaseModel):
    entities: list[ExtractedEntity] = Field(default_factory=list)
    causal_links: list[CausalLink] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_causal_links(cls, data: Any) -> Any:
        if isinstance(data, dict) and "causal_links" in data:
            raw_links = data["causal_links"]
            if isinstance(raw_links, list):
                for item in raw_links:
                    if isinstance(item, dict) and "sentence_id" in item:
                        item["sentence_id"] = int(item["sentence_id"])
        return data


class SynthesizedEquationSpec(BaseModel):
    equation_id: str = ""
    target_var: str
    dependencies: list[str] = Field(default_factory=list)
    smt_expression: str
    natural_language_logic: str = ""
    source_sentence_ids: list[int] = Field(default_factory=list)


class InferredParameterSpec(BaseModel):
    var_id: str
    human_name: str = ""
    sort: str = "real"
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float = 0.0
    source_sentence_ids: list[int] = Field(default_factory=list)


class EquationSynthesisResponse(BaseModel):
    parameters: dict[str, InferredParameterSpec] = Field(default_factory=dict)
    equations: dict[str, SynthesizedEquationSpec] = Field(default_factory=dict)
