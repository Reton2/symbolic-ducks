from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import (
    VariableSort,
)


class RawSentence(BaseModel):
    """Immutable representation of a segmented sentence."""

    index: int
    text: str


class ResolvedConcept(BaseModel):
    """Unified policy concept resolved across all sentences."""

    cid: str
    human_name: str
    sort: VariableSort
    ordinal_levels: dict[int, str] | None = None
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float = 0.0
    sentence_ids: set[int] = Field(default_factory=set)
    source_excerpts: list[str] = Field(default_factory=list)


class SynthesizedParamSpec(BaseModel):
    """Schema for latent parameter minted during equation synthesis."""

    var_id: str = ""
    human_name: str = ""
    sort: VariableSort = VariableSort.REAL
    min_bound: float = 0.0
    max_bound: float = 100.0
    default_value: float = 10.0
    source_sentence_ids: list[int] = Field(default_factory=list)

    @field_validator("sort", mode="before")
    @classmethod
    def coerce_param_sort(cls, v: Any) -> VariableSort:
        if isinstance(v, VariableSort):
            return v
        if not v or str(v).lower() not in ("real", "int", "bool"):
            return VariableSort.REAL
        return VariableSort(str(v).lower())

    @field_validator("min_bound", mode="before")
    @classmethod
    def coerce_min(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("max_bound", mode="before")
    @classmethod
    def coerce_max(cls, v: Any) -> float:
        if v is None:
            return 100.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 100.0

    @field_validator("default_value", mode="before")
    @classmethod
    def coerce_default(cls, v: Any) -> float:
        if v is None:
            return 10.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 10.0

    @field_validator("source_sentence_ids", mode="before")
    @classmethod
    def coerce_sids(cls, v: Any) -> list[int]:
        if v is None:
            return []
        if isinstance(v, (int, str)):
            try:
                return [int(v)]
            except (ValueError, TypeError):
                return []
        res = []
        for x in v:
            try:
                if x is not None:
                    res.append(int(x))
            except (ValueError, TypeError):
                pass
        return res


class SynthesizedEquationSpec(BaseModel):
    equation_id: str = ""
    target_var: str = ""
    dependencies: list[str] = Field(default_factory=list)
    smt_expression: str = ""
    natural_language_logic: str = ""
    source_sentence_ids: list[int] = Field(default_factory=list)

    @field_validator("dependencies", mode="before")
    @classmethod
    def coerce_deps(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(item) for item in v if item is not None]

    @field_validator("source_sentence_ids", mode="before")
    @classmethod
    def coerce_eq_sids(cls, v: Any) -> list[int]:
        if v is None:
            return []
        if isinstance(v, (int, str)):
            try:
                return [int(v)]
            except (ValueError, TypeError):
                return []
        res = []
        for x in v:
            try:
                if x is not None:
                    res.append(int(x))
            except (ValueError, TypeError):
                pass
        return res

    @field_validator("natural_language_logic", "smt_expression", mode="before")
    @classmethod
    def coerce_str_fields(cls, v: Any) -> str:
        return "" if v is None else str(v)


class EquationSynthesisResponse(BaseModel):
    """Strict schema contract for the equation synthesis LLM phase."""

    parameters: dict[str, SynthesizedParamSpec] = Field(default_factory=dict)
    equations: dict[str, SynthesizedEquationSpec] = Field(default_factory=dict)

    @field_validator("parameters", mode="before")
    @classmethod
    def coerce_params_dict(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, list):
            res = {}
            for item in v:
                if isinstance(item, dict):
                    pid = item.get("var_id") or item.get("id") or f"param_{len(res)}"
                    res[pid] = item
            return res
        return v

    @field_validator("equations", mode="before")
    @classmethod
    def coerce_eqs_dict(cls, v: Any) -> dict[str, Any]:
        if v is None:
            return {}
        if isinstance(v, list):
            res = {}
            for item in v:
                if isinstance(item, dict):
                    tid = (
                        item.get("target_var")
                        or item.get("target_id")
                        or f"eq_{len(res)}"
                    )
                    res[tid] = item
            return res
        return v


class CausalLink(BaseModel):
    """Directed dependency link extracted between policy concepts."""

    target_id: str
    parent_ids: list[str] = Field(default_factory=list)
    logic_summary: str = ""
    qualitative_thresholds: list[str] = Field(default_factory=list)
    sentence_id: int = 0

    @field_validator("parent_ids", "qualitative_thresholds", mode="before")
    @classmethod
    def coerce_list(cls, v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return [str(item) for item in v if item is not None]

    @field_validator("sentence_id", mode="before")
    @classmethod
    def coerce_sentence_id(cls, v: Any) -> int:
        if v is None:
            return 0
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0

    @field_validator("logic_summary", mode="before")
    @classmethod
    def coerce_logic_summary(cls, v: Any) -> str:
        return "" if v is None else str(v)


class ExtractedEntity(BaseModel):
    """Entity schema extracted from an LLM sentence batch with resilient coercion."""

    id: str
    name: str = ""
    sort: VariableSort = VariableSort.REAL
    min_bound: float = 0.0
    max_bound: float = 100.0
    ordinal_levels: dict[int, str] | None = None

    @field_validator("sort", mode="before")
    @classmethod
    def coerce_sort(cls, v: Any) -> VariableSort:
        if isinstance(v, VariableSort):
            return v
        if not v or str(v).lower() not in ("real", "int", "bool"):
            return VariableSort.REAL
        return VariableSort(str(v).lower())

    @field_validator("min_bound", mode="before")
    @classmethod
    def coerce_min_bound(cls, v: Any) -> float:
        if v is None:
            return 0.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 0.0

    @field_validator("max_bound", mode="before")
    @classmethod
    def coerce_max_bound(cls, v: Any) -> float:
        if v is None:
            return 100.0
        try:
            return float(v)
        except (ValueError, TypeError):
            return 100.0

    @field_validator("ordinal_levels", mode="before")
    @classmethod
    def coerce_ordinal_levels(cls, v: Any) -> dict[int, str] | None:
        if v is None:
            return None
        if isinstance(v, list):
            return {i: str(item) for i, item in enumerate(v)}
        if isinstance(v, dict):
            return {int(k): str(val) for k, val in v.items()}
        return None

    @model_validator(mode="after")
    def normalize_bounds(self) -> "ExtractedEntity":
        if self.ordinal_levels:
            if self.max_bound == 100.0 or self.max_bound <= self.min_bound:
                self.max_bound = float(len(self.ordinal_levels) - 1)
            self.sort = "int"
        return self


class SentenceMapResponse(BaseModel):
    """Strict schema contract for the sentence mapping LLM phase."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    causal_links: list[CausalLink] = Field(default_factory=list)
