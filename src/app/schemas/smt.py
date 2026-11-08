from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import (
    AbductiveSolveStatus,
    ConstraintOperator,
    CounterfactualStatus,
    DeadLogicClassification,
    VerificationStatus,
)


class VariableSolvedState(BaseModel):
    human_name: str
    value: float | int | bool
    formatted: str
    layer: int = 0


class SolvedModelWitness(BaseModel):
    INPUT: dict[str, VariableSolvedState] = Field(default_factory=dict)
    INTERMEDIATE: dict[str, VariableSolvedState] = Field(default_factory=dict)
    OUTPUT: dict[str, VariableSolvedState] = Field(default_factory=dict)
    PARAMETER: dict[str, VariableSolvedState] = Field(default_factory=dict)


class TargetConstraintSpec(BaseModel):
    op: ConstraintOperator = ConstraintOperator.EQ
    val: float | int | bool | str


class AbductiveSolveResult(BaseModel):
    status: AbductiveSolveStatus
    applied_targets: list[str] = Field(default_factory=list)
    solved_state: SolvedModelWitness | None = None
    message: str = ""


class ChangedInputSpec(BaseModel):
    human_name: str
    previous_value: float | int | bool
    required_value: str


class CounterfactualResult(BaseModel):
    status: CounterfactualStatus
    minimal_input_changes_count: int = 0
    changed_inputs: dict[str, ChangedInputSpec] = Field(default_factory=dict)
    resulting_outputs: dict[str, VariableSolvedState] = Field(default_factory=dict)
    message: str = ""


class DeadLogicDiagnostic(BaseModel):
    target_variable: str
    human_name: str
    target_state: str
    classification: DeadLogicClassification
    explanation: str
    conflicting_equation_ids: list[str] = Field(default_factory=list)
    conflicting_sentence_ids: list[int] = Field(default_factory=list)
    conflicting_sentences_text: list[str] = Field(default_factory=list)
    suggested_remediation: str = ""
    relaxed_parameter_solutions: dict[str, float] = Field(default_factory=dict)


class ReachabilityProof(BaseModel):
    output_var: str
    human_name: str
    target_state: str
    reachable: bool
    diagnostic: DeadLogicDiagnostic | None = None


class GraphVerificationReport(BaseModel):
    status: VerificationStatus
    consistent: bool
    is_dag_consistent: bool = True
    reachable_count: int = 0
    dead_count: int = 0
    dead_state_warnings: list[str] = Field(default_factory=list)
    reachability_proofs: list[ReachabilityProof] = Field(default_factory=list)
