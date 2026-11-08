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
