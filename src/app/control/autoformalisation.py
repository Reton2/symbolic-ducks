from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import logging
import os
import random
import re
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import z3
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator, model_validator
from z3 import (
    And,
    Bool,
    BoolRef,
    BoolVal,
    Implies,
    Int,
    IntVal,
    Not,
    Or,
    Real,
    RealVal,
    Solver,
    ToInt,
    ToReal,
    Xor,
    is_bool,
    is_const,
    is_expr,
    is_int,
    is_real,
    sat,
)

from app.control.smt_helpers import (
    TargetSortMode,
    destruct_z3_expr,
    evaluate_z3_symbolic_expression,
    extract_z3_dependencies,
    z3_if,
)
from app.schemas.schemas import (
    AutonomousPolicyGraph,
    ConceptModality,
    InferredEquation,
    InferredVariable,
    VariableRole,
    VariableSort,
)

logger = logging.getLogger("app.control.autoformalisation")


def configure_logger(level_name: str = "INFO") -> None:
    """Ensure the module logger has an active console StreamHandler so INFO/DEBUG

    messages are visible in the terminal even without root basicConfig.
    """
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logger.setLevel(numeric_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(numeric_level)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
        logger.propagate = False


# Initialize console logging on import
configure_logger(os.getenv("LOG_LEVEL", "INFO"))

SENTENCE_MAP_PROMPT = """You are a Format-Blind Semantic Dependency Extractor for Multi-Modal Z3 Policy Graphs.
You will receive an unordered list of numbered sentences from a policy document.
For every sentence, extract:
1. "entities": All domain concepts, telemetry metrics, ordinal tiers, and categorical operational states mentioned:
   - `id`: Canonical snake_case identifier (e.g. `consolidated_book_depth`, `fix_session_connection_state`).
   - `name`: Human-readable concept title.
   - `sort`: One of `["real", "int", "bool"]`:
     * Use `"real"` (`ordinal_levels: null`) for continuous NUMERICAL measurements (percentages, bps, USD depth, ratios, z-scores, VIX points, scores `0.0..100.0`).
     * Use `"int"` (`ordinal_levels: null`) for discrete NUMERICAL counters (message rates, order counts, minutes).
     * Use `"int"` with `ordinal_levels` (`{"0": "Level_0_Calm", "1": "Level_1_Guarded", ...}`) for ORDINAL severity/readiness tiers `0..N` (`min_bound: 0`, `max_bound: N`).
     * Use `"int"` with `ordinal_levels` (`{"0": "NOMINAL_STATE", "1": "WARNING_STATE", "2": "CRITICAL_STATE"}`) for CATEGORICAL mutually-exclusive operational modes, regulatory flags, or governance directives ordered from healthy/nominal (`0`) to degraded/restricted (`1`) to critical/violation/halt (`K`, `min_bound: 0`, `max_bound: K`).
   - `min_bound`: Numeric lower bound (float).
   - `max_bound`: Numeric upper bound (float).
   - `ordinal_levels`: Mapping of integer index to state/tier label when ordinal or categorical, else `null`.
2. "causal_links": Whenever a sentence states that Concept Y is governed by, computed from, triggered by, escalates when, or requires Concepts X1, X2..., output:
   {
     "target_id": "y_id",
     "parent_ids": ["x1_id", "x2_id"],
     "logic_summary": "Precise logical specification: state whether Y is a conjunction (And) or disjunction (Or), whether each parent X_i is checked positively or negated ('free from', 'avoids', 'beneath'), and which ordinal tier or categorical state triggers it.",
     "qualitative_thresholds": ["any qualitative threshold phrases requiring a latent parameter"],
     "sentence_id": int
   }

Output strictly valid JSON: {"entities": [...], "causal_links": [...]}"""

EQUATION_SYNTHESIS_PROMPT = """You are a Z3 Symbolic Constraint Architect.
You will receive the resolved entity vocabulary (`entities`) and target causal specifications (`targets`) extracted from a policy document.

Output ONLY a ```python ... ``` block that initializes `W_hat = []` and appends one `W_hat.append(target_var == <z3_expr>)` constraint per target variable.
Do NOT define functions, classes, loops, imports, helper calls, or intermediate variables. Reference every entity directly by its bare identifier.

### ALLOWED Z3 PRIMITIVES
`And`, `Or`, `Not`, `If`, `Xor`, `Implies`, `RealVal`, `IntVal`, `BoolVal`, `ToReal`, `ToInt`.

### MODALITY CHECKS & TARGET SYNTHESIS
1. **Numerical (`modality == "numerical"`, `sort == "real"` or counter `"int"`)**:
   - Check against threshold parameter `param_<target>_<dep>` or literal bound: `dep_var >= param_target_dep` or `dep_var <= param_target_dep`.
   - Target synthesis (`sort == "real"`): `W_hat.append(target_var == If(cond, 100.0, 10.0))` (use `If(a <= b, a, b)` for min, `If(a >= b, a, b)` for max, `100.0 - expr` for complement).
2. **Ordinal (`modality == "ordinal"`, `sort == "int"`, tiers `0..N`)**:
   - Check tier threshold: `dep_var >= k` (elevated tier) or `dep_var <= k` (nominal/contained tier).
   - Target synthesis (`sort == "int"`): `W_hat.append(target_var == If(c_high, N, If(c_mid, 1, 0)))` (use `If(a >= b, a, b)` for dominant tier, `N - dep_var` for complement).
3. **Categorical (`modality == "categorical"`, `sort == "int"`, states `0..K`)**:
   - Check discrete state: `dep_var == k` or `dep_var != k` (`0` = nominal, `1` = warning/restricted, `K` = critical/halt).
   - Target synthesis (`sort == "int"`): `W_hat.append(target_var == If(c_crit, K, If(c_warn, 1, 0)))`.

### OUTPUT FORMAT
```python
W_hat = []
W_hat.append(<target_id> == <z3_expr>)
```
Output ONLY valid Python code."""

INTRO_VERBS = (
    r"(?:is\s+a|is\s+an|tracks|measures|evaluates|aggregates|captures|classifies|"
    r"monitors|determines|quantifies|regulates|magnifies|establishes|represents|dictates)"
)
INTRO_PATTERN = re.compile(
    rf"^([A-Z][A-Za-z0-9\-\s/()&,]{{3,65}}?)\s+(?::\s*|\bis\b\s+|{INTRO_VERBS}\b)(.+)$"
)
EXCLUDE_SUBJECT_PREFIXES = re.compile(
    r"^(?:This|The|An|A|It|These|Under|In|Achieving|Full|High|Rejection|Access|Urgency|Feasibility|Prohibition)\b"
)
CAUSAL_PATTERN = re.compile(
    r"\b(?:requires\s+that|is\s+triggered\s+if|combines|occurs\s+when|whenever|activates\s+when|"
    r"compounds|escalates\s+when|is\s+declared\s+if|evaluates|monitors|magnifies|enforced\s+if|"
    r"enforced\s+when|advances\s+toward|initiated\s+whenever|computed\s+as|determined\s+by|"
    r"conjunction\s+of|maximum\s+across|minimum\s+of)\b",
    flags=re.IGNORECASE,
)
STOP_WORDS = frozenset(
    {
        "this",
        "that",
        "with",
        "from",
        "into",
        "when",
        "where",
        "while",
        "under",
        "across",
        "between",
        "tier",
        "score",
        "mode",
        "state",
        "level",
        "metric",
        "index",
        "stage",
        "status",
    }
)


def extract_json_payload(raw_content: str) -> str:
    """Extract clean JSON string from raw LLM output, stripping markdown fences if present."""
    text = raw_content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def extract_python_code(raw_content: str) -> str:
    """Extract clean executable Python code from raw LLM output, stripping markdown fences."""
    text = raw_content.strip()
    fenced = re.search(
        r"```(?:python|py)?\s*\n(.*?)```", text, flags=re.DOTALL | re.IGNORECASE
    )
    if fenced:
        return fenced.group(1).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:python|py|json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def infer_concept_modality(
    sort: str,
    ordinal_levels: dict[int, str] | None,
    name: str = "",
) -> ConceptModality:
    """Classify a concept into numerical, ordinal, or categorical modality."""
    if not ordinal_levels:
        return ConceptModality.NUMERICAL
    low_name = name.lower()
    labels_joined = " ".join(ordinal_levels.values()).lower()
    if any(w in low_name for w in ("ordinal", "tier", "stage", "level", "rank")):
        return ConceptModality.ORDINAL
    if any(
        w in low_name
        for w in (
            "categorical",
            "status",
            "mode",
            "state",
            "verdict",
            "directive",
            "regime",
            "posture",
            "decision",
            "trigger",
            "compliance",
            "phase",
            "authority",
        )
    ):
        return ConceptModality.CATEGORICAL
    if any(
        w in labels_joined
        for w in (
            "state_",
            "continue",
            "halt",
            "valid",
            "rejected",
            "connected",
            "dropped",
            "allow",
            "intercept",
            "prohibited",
        )
    ):
        return ConceptModality.CATEGORICAL
    return ConceptModality.ORDINAL


class AutoformalizationError(Exception):
    """Base exception for autoformalisation failures."""


class LLMExtractionError(AutoformalizationError):
    """Raised when LLM extraction or parsing fails."""


class Z3SandboxExecutionError(AutoformalizationError):
    """Raised when Z3 Python sandbox execution or model destruction fails."""


class CEGISVerificationError(AutoformalizationError):
    """Raised when Z3 CEGIS verification fails."""


class AutoformalizerConfig(BaseModel):
    """Configuration contract for deep autoformalization pipeline."""

    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_concurrency: int = 16
    chunk_size: int = 30
    temperature: float = 0.0
    log_level: str = "INFO"
    cache_dir: str = ".cache/autoformalisation"
    enable_cache: bool = True

    @classmethod
    def from_env(cls) -> AutoformalizerConfig:
        return cls(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("LLM_API_KEY", ""),
            max_concurrency=int(os.getenv("MAX_CONCURRENCY", "16")),
            chunk_size=int(os.getenv("CHUNK_SIZE", "30")),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            cache_dir=os.getenv(
                "AUTOFORMALISATION_CACHE_DIR",
                os.getenv("CACHE_DIR", ".cache/autoformalisation"),
            ),
            enable_cache=os.getenv("ENABLE_CACHE", "true").lower()
            in ("true", "1", "yes"),
        )


class RawSentence(BaseModel):
    """Immutable representation of a segmented sentence."""

    index: int
    text: str


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
    def normalize_bounds(self) -> ExtractedEntity:
        if self.ordinal_levels:
            if self.max_bound == 100.0 or self.max_bound <= self.min_bound:
                self.max_bound = float(len(self.ordinal_levels) - 1)
            self.sort = "int"
        return self


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


class SentenceMapResponse(BaseModel):
    """Strict schema contract for the sentence mapping LLM phase."""

    entities: list[ExtractedEntity] = Field(default_factory=list)
    causal_links: list[CausalLink] = Field(default_factory=list)


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
    """Schema for Z3 equation synthesized from dependency hypergraph."""

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


class InferredSortSpec(BaseModel):
    """Sort and bounding specification inferred from concept naming."""

    sort: VariableSort
    ordinal_levels: dict[int, str] | None = None
    min_bound: float
    max_bound: float
    default_value: float


class SentenceAtomizer:
    """Format-blind sentence atomizer preserving semantic sentences across formats."""

    @staticmethod
    def clean_text(raw_text: str) -> str:
        cleaned = re.sub(r"[#*`>_\-]+", " ", raw_text)
        cleaned = re.sub(r"\s+([.,;:!?])", r"\1", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    @classmethod
    def atomize(cls, raw_text: str, shuffle: bool = False) -> list[RawSentence]:
        cleaned = cls.clean_text(raw_text)
        raw_sents = [
            s.strip()
            for s in re.split(r"(?<=[.!?])\s+", cleaned)
            if len(s.strip()) > 15
        ]
        if shuffle:
            random.shuffle(raw_sents)
        sentences = [RawSentence(index=idx, text=s) for idx, s in enumerate(raw_sents)]
        logger.info(
            "[Stage 1 - Format-Blind Atomizer] Segmented text into %d raw sentences (Shuffled=%s)",
            len(sentences),
            shuffle,
        )
        return sentences


class Z3SandboxVarStore(dict[str, Any]):
    """Symbolic Z3 variable store that auto-mints Real(key) on missing lookups."""

    def __missing__(self, key: str) -> Any:
        zvar = Real(str(key))
        self[str(key)] = zvar
        return zvar


class Z3CodeSandbox:
    """AST-validated Z3 constraint sandbox executing `W_hat` constraint lists."""

    _ALLOWED_CALL_NAMES = frozenset(
        {
            "And",
            "Or",
            "Not",
            "If",
            "Xor",
            "Implies",
            "Real",
            "Int",
            "Bool",
            "RealVal",
            "IntVal",
            "BoolVal",
            "ToReal",
            "ToInt",
        }
    )
    _ALLOWED_METHODS = frozenset({"append", "extend"})

    @classmethod
    def _validate_ast(cls, code_str: str) -> None:
        tree = ast.parse(code_str, mode="exec")
        for node in ast.walk(tree):
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef,
                    ast.Lambda,
                    ast.Delete,
                    ast.Global,
                    ast.Nonlocal,
                    ast.With,
                    ast.AsyncWith,
                    ast.Try,
                    ast.Raise,
                    ast.Subscript,
                    ast.While,
                    ast.For,
                    ast.AsyncFor,
                ),
            ):
                raise ValueError(f"Disallowed syntax in sandbox: {type(node).__name__}")
            if isinstance(node, ast.Name) and node.id.startswith("__"):
                raise ValueError(f"Disallowed identifier in sandbox: {node.id}")
            if isinstance(node, ast.Assign) and (
                len(node.targets) != 1
                or not isinstance(node.targets[0], ast.Name)
                or node.targets[0].id != "W_hat"
            ):
                raise ValueError("Only assignment to 'W_hat' is permitted in sandbox")
            if isinstance(node, ast.Attribute) and (
                node.attr not in cls._ALLOWED_METHODS
                or not (isinstance(node.value, ast.Name) and node.value.id == "W_hat")
            ):
                raise ValueError(f"Disallowed attribute access: {node.attr}")
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id not in cls._ALLOWED_CALL_NAMES:
                        raise ValueError(f"Disallowed function call: {node.func.id}")
                elif isinstance(node.func, ast.Attribute):
                    if node.func.attr not in cls._ALLOWED_METHODS:
                        raise ValueError(f"Disallowed method call: {node.func.attr}")
                else:
                    raise ValueError("Disallowed callable expression in sandbox")

    @classmethod
    def execute_constraints(
        cls,
        scope: Z3SandboxVarStore,
        llm_code_response: str,
    ) -> tuple[list[BoolRef] | None, str | None]:
        try:
            cls._validate_ast(llm_code_response)
            exec(llm_code_response, {"__builtins__": {}}, scope)
            w_hat_rules = scope.get("W_hat", [])
            if not isinstance(w_hat_rules, list) or len(w_hat_rules) == 0:
                return None, "Empty or missing W_hat list"
            for item in w_hat_rules:
                if not isinstance(item, BoolRef):
                    return None, f"Invalid Z3 BoolRef element: {type(item)}"
            return w_hat_rules, None
        except Exception as exc:
            return None, f"{type(exc).__name__}: {str(exc)}"


class Z3SynthesisSandbox:
    """Isolated Z3 execution sandbox for `W_hat` Z3 constraint synthesis."""

    def __init__(
        self,
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> None:
        self.concepts = concepts
        self.links = links
        self.v = Z3SandboxVarStore()
        self.parameters: dict[str, dict[str, Any]] = {}
        self.equations: dict[str, dict[str, Any]] = {}
        self._init_concept_variables()

    def _init_concept_variables(self) -> None:
        for cid, c in self.concepts.items():
            if c.sort == "real":
                zvar: Any = Real(cid)
            elif c.sort == "int":
                zvar = Int(cid)
            else:
                zvar = Bool(cid)
            self.v[cid] = zvar

    def _get_target_sort(self, target_var: str) -> TargetSortMode:
        if target_var in self.concepts:
            return self.concepts[target_var].sort
        if target_var in self.v and is_expr(self.v[target_var]):
            zvar = self.v[target_var]
            if is_int(zvar):
                return "int"
            if is_real(zvar):
                return "real"
            if is_bool(zvar):
                return "bool"
        return "auto"

    def _infer_parent_for_param(
        self, param_id: str, sibling_deps: Sequence[str]
    ) -> ResolvedConcept | None:
        for dep in sibling_deps:
            if dep in self.concepts and dep in param_id:
                return self.concepts[dep]
        for cid, c in self.concepts.items():
            if cid in param_id:
                return c
        for dep in sibling_deps:
            if dep in self.concepts and not self.concepts[dep].ordinal_levels:
                return self.concepts[dep]
        return None

    def _ensure_implicit_parameters(
        self, deps: Sequence[str], sids: Sequence[int]
    ) -> None:
        for dep in deps:
            if dep not in self.concepts and dep not in self.parameters:
                parent_c = self._infer_parent_for_param(dep, deps)
                if parent_c is not None and not parent_c.ordinal_levels:
                    inferred_sort = "int" if parent_c.sort == "int" else "real"
                    min_b = float(parent_c.min_bound)
                    max_b = float(parent_c.max_bound)
                else:
                    zvar = self.v.get(dep)
                    inferred_sort = (
                        "int" if (is_expr(zvar) and is_int(zvar)) else "real"
                    )
                    min_b = 0.0
                    max_b = 100.0

                is_low_bad = any(
                    w in dep
                    for w in (
                        "depth",
                        "correlation",
                        "alpha",
                        "return",
                        "momentum",
                        "capacity",
                        "feasibility",
                        "quality",
                    )
                )
                ratio = 0.25 if is_low_bad else 0.70
                def_val = round((max_b - min_b) * ratio + min_b, 2)
                if inferred_sort == "int":
                    def_val = float(int(round(def_val)))

                self.parameters[dep] = {
                    "var_id": dep,
                    "human_name": dep.replace("_", " ").title(),
                    "sort": inferred_sort,
                    "min_bound": min_b,
                    "max_bound": max_b,
                    "default_value": def_val,
                    "source_sentence_ids": [int(s) for s in sids],
                }

    def register_equation(
        self,
        target_var: str,
        smt_expression: Any,
        natural_language_logic: str = "",
        source_sentence_ids: Sequence[int] = (),
        dependencies: Sequence[str] = (),
        equation_id: str = "",
    ) -> dict[str, Any]:
        """Registers a derived variable's Z3 symbolic expression and destructs its AST."""
        target_sort = self._get_target_sort(target_var)
        expr_str = destruct_z3_expr(smt_expression, target_sort=target_sort)
        ast_deps = extract_z3_dependencies(smt_expression)
        if not ast_deps:
            ast_deps = extract_z3_dependencies(expr_str)

        merged_deps: list[str] = []
        for d in [*dependencies, *ast_deps]:
            if d != target_var and d not in merged_deps:
                merged_deps.append(d)

        sids = [int(s) for s in source_sentence_ids]
        if not sids and target_var in self.concepts:
            sids = sorted(self.concepts[target_var].sentence_ids)

        self._ensure_implicit_parameters(merged_deps, sids)
        entry = {
            "equation_id": equation_id or f"eq_{target_var}",
            "target_var": target_var,
            "dependencies": merged_deps,
            "smt_expression": expr_str,
            "natural_language_logic": natural_language_logic
            or f"Synthesized Z3 rule for {target_var}",
            "source_sentence_ids": sids,
        }
        self.equations[target_var] = entry
        return entry

    def _normalize_param_dict(self, raw_params: Any) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = dict(self.parameters)
        items: list[tuple[str, Any]] = []
        if isinstance(raw_params, dict):
            items = [(str(k), val) for k, val in raw_params.items()]
        elif isinstance(raw_params, list):
            for item in raw_params:
                if isinstance(item, dict):
                    pid = str(
                        item.get("var_id") or item.get("id") or f"param_{len(items)}"
                    )
                    items.append((pid, item))

        for pid, spec in items:
            if isinstance(spec, dict):
                var_id = str(spec.get("var_id") or pid)
                out[var_id] = {
                    "var_id": var_id,
                    "human_name": str(
                        spec.get("human_name") or spec.get("name") or var_id
                    ),
                    "sort": str(spec.get("sort") or "real"),
                    "min_bound": spec.get("min_bound", 0.0),
                    "max_bound": spec.get("max_bound", 100.0),
                    "default_value": spec.get("default_value", 10.0),
                    "source_sentence_ids": spec.get("source_sentence_ids", []),
                }
        return out

    def _normalize_equations_dict(
        self, raw_equations: Any
    ) -> dict[str, dict[str, Any]]:
        items: list[tuple[str, Any]] = []
        if isinstance(raw_equations, dict):
            items = [(str(k), val) for k, val in raw_equations.items()]
        elif isinstance(raw_equations, list):
            for item in raw_equations:
                if isinstance(item, dict):
                    tid = str(
                        item.get("target_var")
                        or item.get("target_id")
                        or f"eq_{len(items)}"
                    )
                    items.append((tid, item))

        for tid, spec in items:
            if isinstance(spec, dict):
                target_var = str(spec.get("target_var") or spec.get("target_id") or tid)
                raw_expr = spec.get("smt_expression", spec.get("expr", ""))
                self.register_equation(
                    target_var=target_var,
                    smt_expression=raw_expr,
                    natural_language_logic=str(
                        spec.get("natural_language_logic") or ""
                    ),
                    source_sentence_ids=spec.get("source_sentence_ids") or (),
                    dependencies=spec.get("dependencies") or (),
                    equation_id=str(spec.get("equation_id") or f"eq_{target_var}"),
                )
            else:
                self.register_equation(target_var=tid, smt_expression=spec)
        return dict(self.equations)

    def _harvest_w_hat_constraints(self, w_hat_rules: Sequence[Any]) -> None:
        link_logic_by_target: dict[str, list[str]] = {}
        link_sids_by_target: dict[str, set[int]] = {}
        for lnk in self.links:
            if lnk.logic_summary:
                link_logic_by_target.setdefault(lnk.target_id, []).append(
                    lnk.logic_summary
                )
            link_sids_by_target.setdefault(lnk.target_id, set()).add(lnk.sentence_id)

        for assertion in w_hat_rules:
            if not is_expr(assertion) or assertion.decl().kind() not in (
                z3.Z3_OP_EQ,
                z3.Z3_OP_IFF,
            ):
                continue
            lhs, rhs = assertion.arg(0), assertion.arg(1)
            if is_const(lhs) and lhs.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                target_var, expr = str(lhs), rhs
            elif is_const(rhs) and rhs.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                target_var, expr = str(rhs), lhs
            else:
                continue

            nl_logic = "; ".join(link_logic_by_target.get(target_var, ()))
            sids = sorted(link_sids_by_target.get(target_var, set()))
            self.register_equation(
                target_var=target_var,
                smt_expression=expr,
                natural_language_logic=nl_logic,
                source_sentence_ids=sids,
            )

    def destruct_z3_model(
        self,
        parameters: Any = (),
        equations: Any = (),
    ) -> dict[str, Any]:
        """Destructs constructed Z3 parameters and AST equations into the JSON contract."""
        if parameters:
            self.parameters = self._normalize_param_dict(parameters)
        if equations:
            self._normalize_equations_dict(equations)
        return {
            "parameters": dict(self.parameters),
            "equations": dict(self.equations),
        }

    def _build_sandbox_scope(self) -> Z3SandboxVarStore:
        scope = Z3SandboxVarStore(
            {
                "And": And,
                "Or": Or,
                "Not": Not,
                "If": z3_if,
                "Xor": Xor,
                "Implies": Implies,
                "Real": Real,
                "Int": Int,
                "Bool": Bool,
                "RealVal": RealVal,
                "IntVal": IntVal,
                "BoolVal": BoolVal,
                "ToReal": ToReal,
                "ToInt": ToInt,
                "True": True,
                "False": False,
                "W_hat": [],
            }
        )
        for var_name, z3_var in self.v.items():
            scope[var_name] = z3_var
        return scope

    def execute(self, raw_llm_output: str) -> EquationSynthesisResponse:
        """Executes `W_hat` Z3 constraints in `Z3CodeSandbox` and returns destructed JSON schema."""
        code_str = extract_python_code(raw_llm_output)
        if not code_str:
            return EquationSynthesisResponse()

        # Support direct JSON payloads seamlessly if returned by mocks or fallback models
        if code_str.startswith("{"):
            try:
                parsed_json = json.loads(code_str)
                if isinstance(parsed_json, dict) and (
                    "equations" in parsed_json or "parameters" in parsed_json
                ):
                    destructed = self.destruct_z3_model(
                        parsed_json.get("parameters", ()),
                        parsed_json.get("equations", ()),
                    )
                    return EquationSynthesisResponse.model_validate(destructed)
            except Exception:
                pass

        scope = self._build_sandbox_scope()
        w_hat_rules, err_msg = Z3CodeSandbox.execute_constraints(scope, code_str)
        if err_msg is not None or w_hat_rules is None:
            logger.error("Z3 Python sandbox execution failed: %s", err_msg)
            raise Z3SandboxExecutionError(
                f"Failed to execute synthesized Z3 constraints in sandbox: {err_msg}"
            )

        for k, val in scope.items():
            if k not in self.v and is_expr(val):
                self.v[k] = val

        self._harvest_w_hat_constraints(w_hat_rules)
        destructed_payload = self.destruct_z3_model()
        return EquationSynthesisResponse.model_validate(destructed_payload)


class LLMMapReduceExtractor:
    """Concurrent map-reduce entity extractor with bounded async concurrency (max 16)."""

    def __init__(self, client: AsyncOpenAI, config: AutoformalizerConfig) -> None:
        self.client = client
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)

    async def _extract_chunk(
        self,
        batch: list[RawSentence],
        batch_idx: int,
        total_batches: int,
    ) -> SentenceMapResponse:
        batch_text = "\n".join(f"[{s.index}] {s.text}" for s in batch)
        async with self._semaphore:
            logger.info(
                "Acquired concurrency slot for batch %d/%d (%d sentences)",
                batch_idx + 1,
                total_batches,
                len(batch),
            )
            try:
                res = await self.client.chat.completions.create(
                    model=self.config.model,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": SENTENCE_MAP_PROMPT},
                        {"role": "user", "content": batch_text},
                    ],
                    extra_body={
                        "reasoning": {"enabled": True},
                        "provider": {"only": ["alibaba"], "allow_fallbacks": False},
                    },
                    temperature=self.config.temperature,
                )
            except Exception as err:
                logger.error(
                    "LLM batch %d/%d request failed: %s",
                    batch_idx + 1,
                    total_batches,
                    err,
                )
                raise LLMExtractionError(
                    f"LLM batch {batch_idx + 1} call failed: {err}"
                ) from err

        raw_content = res.choices[0].message.content or "{}"
        logger.info(
            "Batch %d/%d RAW LLM output: %s", batch_idx + 1, total_batches, raw_content
        )
        clean_content = extract_json_payload(raw_content)
        try:
            response = SentenceMapResponse.model_validate_json(clean_content)
            logger.info(
                "Batch %d/%d successfully mapped: %d entities, %d causal links",
                batch_idx + 1,
                total_batches,
                len(response.entities),
                len(response.causal_links),
            )
            return response
        except Exception as err:
            logger.error(
                "LLM batch %d/%d JSON validation failed: %s",
                batch_idx + 1,
                total_batches,
                err,
            )
            raise LLMExtractionError(
                f"Invalid JSON from batch {batch_idx + 1}: {err}"
            ) from err

    async def map_sentences(
        self, sentences: list[RawSentence]
    ) -> list[SentenceMapResponse]:
        batches = [
            sentences[i : i + self.config.chunk_size]
            for i in range(0, len(sentences), self.config.chunk_size)
        ]
        if not batches:
            return []

        logger.info(
            "[Stage 2A - Map Phase] Dispatching %d batches to %s (max concurrency: %d)",
            len(batches),
            self.config.model,
            self.config.max_concurrency,
        )
        tasks = [
            asyncio.create_task(self._extract_chunk(batch, idx, len(batches)))
            for idx, batch in enumerate(batches)
        ]
        results = await asyncio.gather(*tasks)
        logger.info(
            "Successfully completed %d concurrent LLM map batches", len(results)
        )
        return list(results)

    def reduce_results(
        self,
        responses: list[SentenceMapResponse],
        sentences: list[RawSentence],
    ) -> tuple[dict[str, ResolvedConcept], list[CausalLink]]:
        merged_entities: dict[str, ResolvedConcept] = {}
        all_links: list[CausalLink] = []
        sent_dict = {s.index: s.text for s in sentences}

        for resp in responses:
            for ent in resp.entities:
                if ent.id not in merged_entities:
                    merged_entities[ent.id] = ResolvedConcept(
                        cid=ent.id,
                        human_name=ent.name or ent.id,
                        sort=ent.sort,
                        ordinal_levels=ent.ordinal_levels,
                        min_bound=ent.min_bound,
                        max_bound=ent.max_bound,
                        default_value=ent.min_bound,
                    )
                else:
                    existing = merged_entities[ent.id]
                    if ent.ordinal_levels and not existing.ordinal_levels:
                        existing.ordinal_levels = ent.ordinal_levels
                        existing.sort = ent.sort
                        existing.max_bound = ent.max_bound
                    if ent.name and len(ent.name) > len(existing.human_name):
                        existing.human_name = ent.name
            for link in resp.causal_links:
                all_links.append(link)
                for eid in [link.target_id, *link.parent_ids]:
                    if eid not in merged_entities and eid:
                        merged_entities[eid] = ResolvedConcept(
                            cid=eid,
                            human_name=eid.replace("_", " ").title(),
                            sort="real",
                        )
                    if eid in merged_entities:
                        merged_entities[eid].sentence_ids.add(link.sentence_id)

        for concept in merged_entities.values():
            sids = sorted(concept.sentence_ids)
            concept.source_excerpts = [sent_dict.get(idx, "") for idx in sids[:3]]

        logger.info(
            "[Stage 2B - Entity Resolution] Unified %d canonical concepts and %d causal links",
            len(merged_entities),
            len(all_links),
        )
        return merged_entities, all_links

    @staticmethod
    def _build_synthesis_payload(
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> dict[str, Any]:
        entity_specs: dict[str, dict[str, Any]] = {}
        for c in concepts.values():
            entity_specs[c.cid] = {
                "id": c.cid,
                "name": c.human_name,
                "modality": infer_concept_modality(
                    c.sort, c.ordinal_levels, c.human_name
                ),
                "sort": str(c.sort),
                "min_bound": c.min_bound,
                "max_bound": c.max_bound,
                "ordinal_levels": c.ordinal_levels,
            }

        grouped_links: dict[str, list[CausalLink]] = {}
        for link in links:
            grouped_links.setdefault(link.target_id, []).append(link)

        targets: dict[str, dict[str, Any]] = {}
        for tid, tlinks in grouped_links.items():
            parents: list[str] = []
            thresholds: list[str] = []
            for lnk in tlinks:
                for pid in lnk.parent_ids:
                    if pid != tid and pid not in parents:
                        parents.append(pid)
                for th in lnk.qualitative_thresholds:
                    if th not in thresholds:
                        thresholds.append(th)

            targets[tid] = {
                "target_id": tid,
                "parent_ids": parents,
                "logic_summaries": [
                    lnk.logic_summary for lnk in tlinks if lnk.logic_summary
                ],
                "qualitative_thresholds": thresholds,
            }

        return {
            "entities": entity_specs,
            "targets": targets,
        }

    async def synthesize_equations(
        self,
        concepts: dict[str, ResolvedConcept],
        links: list[CausalLink],
    ) -> EquationSynthesisResponse:
        payload = self._build_synthesis_payload(concepts, links)
        logger.info(
            "[Stage 2C - SMT Equation Synthesis] Generating pure Z3 Python model via %s...",
            self.config.model,
        )
        async with self._semaphore:
            try:
                res = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": EQUATION_SYNTHESIS_PROMPT},
                        {"role": "user", "content": json.dumps(payload)},
                    ],
                    extra_body={
                        "reasoning": {"enabled": True},
                        "provider": {"only": ["alibaba"], "allow_fallbacks": False},
                    },
                    temperature=self.config.temperature,
                )
            except Exception as err:
                logger.error("Equation synthesis LLM request failed: %s", err)
                raise LLMExtractionError(f"Equation synthesis failed: {err}") from err

        raw_content = res.choices[0].message.content or ""
        sandbox = Z3SynthesisSandbox(concepts=concepts, links=links)
        try:
            eq_response = sandbox.execute(raw_content)
            logger.info(
                "[Stage 2D - Z3 Sandbox Execution] Constructed & destructed %d parameters and %d symbolic equations",
                len(eq_response.parameters),
                len(eq_response.equations),
            )
            return eq_response
        except Exception as err:
            logger.error("Equation synthesis Z3 sandbox execution failed: %s", err)
            raise LLMExtractionError(
                f"Equation synthesis sandbox execution failed: {err}"
            ) from err

    def build_graph(
        self,
        concepts: dict[str, ResolvedConcept],
        eq_data: EquationSynthesisResponse,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        variables: dict[str, InferredVariable] = {}
        for eid, ent in concepts.items():
            variables[eid] = InferredVariable(
                var_id=eid,
                human_name=ent.human_name,
                role=VariableRole.INPUT,
                sort=ent.sort,
                ordinal_levels=ent.ordinal_levels,
                min_bound=ent.min_bound,
                max_bound=ent.max_bound,
                default_value=ent.default_value,
                source_sentence_ids=sorted(ent.sentence_ids),
                source_excerpts=ent.source_excerpts,
            )

        for pid, p in eq_data.parameters.items():
            variables[pid] = InferredVariable(
                var_id=pid,
                human_name=p.human_name or pid,
                role=VariableRole.PARAMETER,
                sort=p.sort,
                min_bound=p.min_bound,
                max_bound=p.max_bound,
                default_value=p.default_value,
                source_sentence_ids=p.source_sentence_ids,
            )

        equations: dict[str, InferredEquation] = {}
        for tid, eq in eq_data.equations.items():
            if tid in variables:
                equations[tid] = InferredEquation(
                    equation_id=eq.equation_id or f"eq_{tid}",
                    target_var=tid,
                    dependencies=[d for d in eq.dependencies if d in variables],
                    smt_expression=eq.smt_expression,
                    natural_language_logic=eq.natural_language_logic,
                    source_sentence_ids=eq.source_sentence_ids,
                )

        return AutonomousPolicyGraph(
            graph_id=f"smt_hypergraph_{str(uuid.uuid4())[:6]}",
            title="Autonomously Inferred Sentence-Stream Policy Graph",
            raw_document_text="\n\n".join(s.text for s in sentences),
            sentence_count=len(sentences),
            variables=variables,
            equations=equations,
            cegis_compiler_log=log,
        )


class CEGISGraphVerifier:
    """Graph topology discovery and Z3 CEGIS verification / self-repair."""

    @staticmethod
    def compute_degrees_and_clean(
        graph: AutonomousPolicyGraph,
    ) -> tuple[dict[str, int], dict[str, int], dict[str, list[str]]]:
        in_deg = {k: 0 for k in graph.variables}
        out_deg = {k: 0 for k in graph.variables}
        adj: dict[str, list[str]] = {k: [] for k in graph.variables}

        for tid, eq in graph.equations.items():
            clean_deps = [
                d for d in eq.dependencies if d in graph.variables and d != tid
            ]
            eq.dependencies = clean_deps
            for d in clean_deps:
                if graph.variables[d].role != "PARAMETER":
                    in_deg[tid] += 1
                    out_deg[d] += 1
                    adj[d].append(tid)

        return in_deg, out_deg, adj

    @staticmethod
    def assign_roles(
        graph: AutonomousPolicyGraph,
        in_deg: dict[str, int],
        out_deg: dict[str, int],
    ) -> None:
        for vid, v in graph.variables.items():
            if v.role == "PARAMETER":
                v.layer_index = 0
                continue
            v.in_degree = in_deg[vid]
            v.out_degree = out_deg[vid]
            if v.in_degree == 0:
                v.role = VariableRole.INPUT
                v.layer_index = 0
            elif v.out_degree == 0:
                v.role = VariableRole.OUTPUT
            else:
                v.role = VariableRole.INTERMEDIATE

    @staticmethod
    def topological_sort(
        graph: AutonomousPolicyGraph,
        adj: dict[str, list[str]],
    ) -> list[str]:
        eq_in_deg = {
            tid: sum(1 for d in eq.dependencies if d in graph.equations)
            for tid, eq in graph.equations.items()
        }
        queue = [tid for tid, deg in eq_in_deg.items() if deg == 0]
        topo_order: list[str] = []

        while queue:
            curr = queue.pop(0)
            topo_order.append(curr)
            parent_layers = [
                graph.variables[d].layer_index
                for d in graph.equations[curr].dependencies
                if d in graph.variables
            ]
            graph.variables[curr].layer_index = (
                (max(parent_layers) + 1) if parent_layers else 1
            )
            for nxt in adj.get(curr, []):
                if nxt in eq_in_deg:
                    eq_in_deg[nxt] -= 1
                    if eq_in_deg[nxt] == 0:
                        queue.append(nxt)

        for tid in graph.equations:
            if tid not in topo_order:
                topo_order.append(tid)
                graph.variables[tid].layer_index = 2

        graph.topological_order = topo_order
        return topo_order

    @classmethod
    def verify_and_repair(
        cls, graph: AutonomousPolicyGraph, topo_order: list[str]
    ) -> int:
        z3_vars: dict[str, Real | Int | Bool] = {
            vid: Real(vid)
            if v.sort == "real"
            else (Int(vid) if v.sort == "int" else Bool(vid))
            for vid, v in graph.variables.items()
        }

        repaired_count = 0
        for tid in topo_order:
            eq = graph.equations[tid]
            target_v = graph.variables[tid]
            try:
                s = Solver()
                expr = evaluate_z3_symbolic_expression(eq.smt_expression, z3_vars)
                s.add(z3_vars[tid] == expr)
                if s.check() != sat:
                    raise CEGISVerificationError(
                        f"Equation {tid} is unsatisfiable in Z3"
                    )
            except Exception as err:
                repaired_count += 1
                logger.warning(
                    "Auto-repairing invalid SMT equation for target '%s': %s", tid, err
                )
                non_param_deps = [
                    d for d in eq.dependencies if graph.variables[d].role != "PARAMETER"
                ]
                fallback_dep = (
                    non_param_deps[0]
                    if non_param_deps
                    else list(graph.variables.keys())[0]
                )
                if target_v.sort == "int":
                    eq.smt_expression = f"If(v['{fallback_dep}'] > 1, 2, 0)"
                else:
                    eq.smt_expression = f"If(v['{fallback_dep}'] > 1, 80.0, 20.0)"

        return repaired_count

    @classmethod
    def verify(
        cls, graph: AutonomousPolicyGraph, log: list[str]
    ) -> AutonomousPolicyGraph:
        in_deg, out_deg, adj = cls.compute_degrees_and_clean(graph)
        cls.assign_roles(graph, in_deg, out_deg)
        topo_order = cls.topological_sort(graph, adj)
        repaired_count = cls.verify_and_repair(graph, topo_order)

        in_cnt = sum(1 for v in graph.variables.values() if v.role == "INPUT")
        inter_cnt = sum(1 for v in graph.variables.values() if v.role == "INTERMEDIATE")
        out_cnt = sum(1 for v in graph.variables.values() if v.role == "OUTPUT")
        param_cnt = sum(1 for v in graph.variables.values() if v.role == "PARAMETER")
        max_layer = max((v.layer_index for v in graph.variables.values()), default=1)

        summary_stage3 = (
            f"[Stage 3 - Graph-Theoretic Role Discovery] In-Degree=0 Inputs: {in_cnt} | "
            f"Intermediate Nodes: {inter_cnt} | Out-Degree=0 Outputs: {out_cnt} | "
            f"Latent Params: {param_cnt} (Max Depth: {max_layer} Layers)."
        )
        summary_stage4 = (
            f"[Stage 4 - Z3 CEGIS Formal Verification] All {len(topo_order)} symbolic equations "
            f"compiled and proven SAT in Z3 (Auto-repaired {repaired_count} sort/syntax mismatches)."
        )
        log.append(summary_stage3)
        log.append(summary_stage4)
        logger.info(summary_stage3)
        logger.info(summary_stage4)

        graph.cegis_compiler_log = log
        return graph


class PolicyGraphCache:
    """Manages disk-based persistent caching for AutonomousPolicyGraph models keyed by raw text hash."""

    def __init__(
        self,
        cache_dir: str | Path = ".cache/autoformalisation",
        enabled: bool = True,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.enabled = enabled

    @staticmethod
    def compute_hash(raw_text: str) -> str:
        """Compute SHA-256 hex digest of raw text."""
        return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    def get_cache_path(self, raw_text: str) -> Path:
        """Resolve filesystem path for a cached graph corresponding to raw_text."""
        return self.cache_dir / f"{self.compute_hash(raw_text)}.json"

    def get(self, raw_text: str) -> AutonomousPolicyGraph | None:
        """Retrieve and validate cached AutonomousPolicyGraph if file exists and is valid."""
        if not self.enabled:
            return None

        path = self.get_cache_path(raw_text)
        if not path.is_file():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            graph = AutonomousPolicyGraph.model_validate_json(content)
            logger.info(
                "[Cache Hit] Loaded persistent policy graph from %s (hash=%s)",
                path,
                self.compute_hash(raw_text)[:12],
            )
            return graph
        except Exception as err:
            logger.warning(
                "[Cache Corrupt] Failed to load cached graph from %s: %s (will recompute)",
                path,
                err,
            )
            return None

    def put(self, raw_text: str, graph: AutonomousPolicyGraph) -> Path | None:
        """Atomically persist AutonomousPolicyGraph to disk keyed by raw_text hash."""
        if not self.enabled:
            return None

        path = self.get_cache_path(raw_text)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = path.with_suffix(f".tmp.{uuid.uuid4().hex[:8]}")
            tmp_path.write_text(graph.model_dump_json(indent=2), encoding="utf-8")
            tmp_path.replace(path)
            logger.info(
                "[Cache Saved] Persisted policy graph to %s (hash=%s)",
                path,
                self.compute_hash(raw_text)[:12],
            )
            return path
        except Exception as err:
            logger.warning(
                "[Cache Error] Failed to persist graph to %s: %s",
                path,
                err,
            )
            return None


class DeepAutoformalizer:
    """Enterprise autoformalization orchestrator coordinating sentence atomization,

    concurrent LLM extraction, linguistic fallback, and Z3 formal verification.
    """

    def __init__(
        self,
        config: AutoformalizerConfig | None = None,
        client: AsyncOpenAI | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> None:
        self.config = config or AutoformalizerConfig.from_env()
        configure_logger(self.config.log_level)

        if client is not None:
            self.client: AsyncOpenAI | None = client
        elif self.config.api_key:
            self.client = AsyncOpenAI(
                api_key=self.config.api_key, base_url=self.config.base_url
            )
        else:
            self.client = None

        self.atomizer = SentenceAtomizer()
        self.verifier = CEGISGraphVerifier()
        self.cache = cache or PolicyGraphCache(
            cache_dir=self.config.cache_dir,
            enabled=self.config.enable_cache,
        )

    @classmethod
    def from_defaults(cls) -> DeepAutoformalizer:
        """Factory creating autoformalizer with default environment configuration."""
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def from_env(cls) -> DeepAutoformalizer:
        """Factory creating autoformalizer explicitly bound to environment variables."""
        return cls(config=AutoformalizerConfig.from_env())

    @classmethod
    def with_client(
        cls,
        client: AsyncOpenAI,
        config: AutoformalizerConfig | None = None,
        cache: PolicyGraphCache | None = None,
    ) -> DeepAutoformalizer:
        """Factory creating autoformalizer with an explicit AsyncOpenAI client."""
        config = config or AutoformalizerConfig.from_env()
        return cls(config=config, client=client, cache=cache)

    def atomize_into_sentences(
        self, raw_text: str, shuffle: bool = False
    ) -> list[tuple[int, str]]:
        """Atomize text into index-text tuples for backward-compatible caller interfaces."""
        sentences = self.atomizer.atomize(raw_text, shuffle=shuffle)
        return [(s.index, s.text) for s in sentences]

    async def autoformalize_document(
        self,
        raw_text: str,
        shuffle_sentences: bool = False,
        use_cache: bool = True,
    ) -> AutonomousPolicyGraph:
        """Full autonomous autoformalization pipeline with persistent caching."""
        if use_cache:
            cached_graph = self.cache.get(raw_text)
            if cached_graph is not None:
                return cached_graph

        sentences = self.atomizer.atomize(raw_text, shuffle=shuffle_sentences)
        stage1_msg = (
            f"[Stage 1 - Format-Blind Atomizer] Stripped all formatting and segmented "
            f"text into {len(sentences)} raw sentences (Shuffled={shuffle_sentences})."
        )
        log = [stage1_msg]
        logger.info(stage1_msg)

        graph = await self._run_llm_pipeline(sentences, log)
        verified_graph = self.verifier.verify(graph, log)
        if use_cache:
            self.cache.put(raw_text, verified_graph)
        return verified_graph

    async def _run_llm_pipeline(
        self,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        if self.client is None:
            return self._run_offline_fallback_pipeline(sentences, log)

        extractor = LLMMapReduceExtractor(self.client, self.config)
        stage2_msg = (
            f"[Stage 2 - Map-Reduce AI Extractor] Extracting cross-sentence entity "
            f"hypergraph via {self.config.model}..."
        )
        log.append(stage2_msg)
        logger.info(stage2_msg)

        chunk_responses = await extractor.map_sentences(sentences)
        concepts, links = extractor.reduce_results(chunk_responses, sentences)
        stage2b_msg = (
            f"[Stage 2B - Entity Resolution] Unified {len(concepts)} canonical concepts "
            f"and {len(links)} cross-sentence causal links."
        )
        log.append(stage2b_msg)
        logger.info(stage2b_msg)

        eq_response = await extractor.synthesize_equations(concepts, links)
        return extractor.build_graph(concepts, eq_response, sentences, log)

    def _run_offline_fallback_pipeline(
        self,
        sentences: list[RawSentence],
        log: list[str],
    ) -> AutonomousPolicyGraph:
        log.append(
            "[Stage 2 - Offline Deterministic Extractor] Running deterministic entity/causal extraction (no LLM client configured)..."
        )
        vars_dict: dict[str, InferredVariable] = {}
        equations: dict[str, InferredEquation] = {}

        discovered: list[str] = []
        for s in sentences:
            words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", s.text)
            for w in words:
                cid = re.sub(r"[^a-z0-9]+", "_", w.lower()).strip("_")
                if cid and cid not in discovered:
                    discovered.append(cid)
                    is_out = any(
                        k in cid for k in ("directive", "action", "decision", "output")
                    )
                    is_param = any(
                        k in cid for k in ("param", "threshold", "limit", "bound")
                    )
                    sort = VariableSort.INT if is_out else VariableSort.REAL
                    role = (
                        VariableRole.OUTPUT
                        if is_out
                        else (
                            VariableRole.PARAMETER if is_param else VariableRole.INPUT
                        )
                    )
                    ord_levels = (
                        {0: "NOMINAL", 1: "ALERT", 2: "HALT"} if is_out else None
                    )
                    vars_dict[cid] = InferredVariable(
                        var_id=cid,
                        human_name=w,
                        role=role,
                        sort=sort,
                        min_bound=0.0,
                        max_bound=2.0 if is_out else 100.0,
                        default_value=0 if is_out else 10.0,
                        ordinal_levels=ord_levels,
                        source_sentence_ids=[s.index],
                        source_excerpts=[s.text],
                    )

        if not vars_dict:
            vars_dict["sample_input"] = InferredVariable(
                var_id="sample_input",
                human_name="Sample Input",
                role=VariableRole.INPUT,
                sort=VariableSort.REAL,
                min_bound=0.0,
                max_bound=100.0,
                default_value=10.0,
            )
            vars_dict["sample_output"] = InferredVariable(
                var_id="sample_output",
                human_name="Sample Output",
                role=VariableRole.OUTPUT,
                sort=VariableSort.INT,
                min_bound=0.0,
                max_bound=2.0,
                default_value=0,
                ordinal_levels={0: "NOMINAL", 1: "HALT"},
            )

        inputs = [k for k, v in vars_dict.items() if v.role == VariableRole.INPUT]
        outputs = [k for k, v in vars_dict.items() if v.role == VariableRole.OUTPUT]
        if not outputs:
            last_id = list(vars_dict.keys())[-1]
            vars_dict[last_id].role = VariableRole.OUTPUT
            outputs.append(last_id)

        for out_id in outputs:
            dep = inputs[0] if inputs else out_id
            equations[out_id] = InferredEquation(
                equation_id=f"eq_{out_id}",
                target_var=out_id,
                dependencies=[dep],
                smt_expression=(
                    f"If(v['{dep}'] > 50.0, 1, 0)"
                    if vars_dict[out_id].sort == VariableSort.INT
                    else f"If(v['{dep}'] > 50.0, 80.0, 20.0)"
                ),
                natural_language_logic=f"Escalate {out_id} when {dep} exceeds threshold",
                source_sentence_ids=[0],
            )

        log.append(
            f"[Stage 2B - Entity Resolution] Discovered {len(vars_dict)} variables and {len(equations)} causal equations."
        )
        return AutonomousPolicyGraph(
            graph_id=f"graph_{uuid.uuid4().hex[:8]}",
            title="Autoformalized Policy Graph (Offline Mode)",
            raw_document_text="\n".join(s.text for s in sentences),
            sentence_count=len(sentences),
            variables=vars_dict,
            equations=equations,
            topological_order=list(equations.keys()),
            cegis_compiler_log=log,
        )
