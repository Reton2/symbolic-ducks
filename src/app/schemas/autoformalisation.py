from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.enums import VariableRole, VariableSort


class InferredVariable(BaseModel):
    var_id: str
    human_name: str
    role: VariableRole
    in_degree: int = 0
    out_degree: int = 0
    layer_index: int = 0
    sort: VariableSort
    ordinal_levels: dict[int, str] | None = None
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float | int | bool = 0.0
    source_sentence_ids: list[int] = Field(default_factory=list)
    source_excerpts: list[str] = Field(default_factory=list)


class InferredEquation(BaseModel):
    equation_id: str
    target_var: str
    dependencies: list[str] = Field(default_factory=list)
    smt_expression: str
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
