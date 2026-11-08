from __future__ import annotations

CLAUSE_DECOMPOSITION_PROMPT = (
    "You are a Precision Legal & Quantitative Policy Decomposer. "
    "Break the provided raw text into self-contained, atomic Semantic Clauses. "
    "Ignore formatting noise (broken tables, page headers). "
    "For every indicator definition, global desk calculation rule, or gateway/regime/control/arbiter/directive rule, "
    "create one self-contained SemanticClause that preserves every threshold, number, tier name, and condition."
)

ONTOLOGY_EXTRACTION_PROMPT = (
    "You are a Quantitative Ontology Architect. Extract the complete inventory of "
    "all policy entities (inputs, intermediate gateways/regimes/controls/arbiters, and final outputs) "
    "and the Global Policy Calculation Framework.\n\n"
    "CRITICAL RULES:\n"
    "1. Include EVERY primary surveillance indicator (inputs), EVERY intermediate derived assessment, and EVERY final directive.\n"
    "2. NUMERICAL FAITHFULNESS (EVERYTHING WITH A NUMBER STAYS A NUMBER):\n"
    "   - Any entity that measures, calculates, or pools a continuous numerical quantity, score, percentage, index, multiplier, or factor "
    "MUST be `modality='numerical'` and `z3_sort='real'` with bounds [0.0, 100.0] "
    "(or its physical continuous bounds like USD, bps, %, sigma).\n"
    "   - Everything with a number is supposed to stay a number. NEVER classify a numerical calculation as ordinal or categorical.\n"
    "3. EXPLICIT ORDINAL SCALES:\n"
    "   - Ordinal scales (`modality='ordinal'`, `z3_sort='int'`) are ALWAYS explicit in the document with an enumerated list of named discrete tiers/ranks. "
    "Populate `discrete_states` ordered from 0 (lowest/nominal) to K (highest/most severe) with their calibrated 0.0..100.0 risk intensity scores.\n"
    "4. CATEGORICAL STATES:\n"
    "   - Categorical entities (`modality='categorical'`, `z3_sort='int'`) are strictly for discrete operational/governance modes with explicit named states.\n"
    "5. For canonical_id, use clean snake_case of the entity's proper name ONLY.\n"
    "6. For numerical inputs, populate `numerical_mapping` with the exact breach operator, cutoff threshold, breach intensity (100.0), baseline intensity (e.g., 10.0, 15.0, 20.0), and any inverted vulnerability score."
)

DEPENDENCY_MAPPING_PROMPT = (
    "You are a Causal Dependency Graph Mapper. For each target derived entity listed, "
    "identify every Semantic Clause that governs its calculation (including global calculation rules "
    "and any acute/emergency override clauses), and list the exact `canonical_id` of every "
    "input/intermediate entity involved in computing it.\n\n"
    "CRITICAL HIERARCHICAL LINEAGE RULES:\n"
    "1. STRICT LAYER PRECEDENCE FOR OUTPUT DIRECTIVES: Final output actions / directives (role='output') "
    "MUST depend strictly on their governing arbiters / controls (role='intermediate'). "
    "Do NOT pull raw foundational indicators (role='input') into output directives unless the policy explicitly "
    "specifies a 'Direct Circuit Breaker Override' that directly halts or flattens without going through governing arbiters.\n"
    "2. Intermediates pool primary inputs and lower-layer intermediates. Output directives evaluate those pooled arbiters."
)

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a Formal Verification & SMT Policy Synthesis Agent. "
    "Construct a typed `LogicExpr` AST (`expr_ast`) that computes the exact value of the target variable.\n\n"
    "AST CONSTRUCTION RULES:\n"
    "1. CONTINUOUS NUMERICAL FAITHFULNESS (NUMBERS STAY NUMBERS):\n"
    "   - Ordinal scales are always explicit in the document; everything with a number is supposed to stay a number.\n"
    "   - If the target is numerical (`z3_sort == 'real'`), return the exact continuous numerical expression or pooled intensity "
    "(`min_pool`, `max_pool`, `complement_100`, `var_intensity`, `compare`, `literal_real`). "
    "NEVER artificially quantize, step, or bin a continuous numerical metric into ordinal integer tiers! Output the pure mathematical expression directly.\n"
    "2. DUAL CONTINUOUS REPRESENTATION FOR EXPLICIT ORDINAL/CATEGORICAL INTERMEDIATES:\n"
    "   - When an intermediate entity explicitly possesses discrete ordinal tiers or categorical states (0..K where `z3_sort == 'int'`), you MUST provide:\n"
    "     (a) `continuous_intensity_ast`: the exact, un-quantized 0.0..100.0 continuous pooled expression (`min_pool` / `max_pool` over input intensities) BEFORE any discretization.\n"
    "     (b) `expr_ast`: the discrete tier integer ITE ladder (0..max_bound) mapped from that continuous intensity.\n"
    "   - This guarantees that downstream nodes pool the true continuous intensity without losing precision to coarse tier step-quantization.\n"
    "3. PURE POOLING OVER CONTINUOUS INTENSITIES:\n"
    "   - Always use `var_intensity` with `var_id` (and `invert_intensity=True` when converting risk to health = 100.0 - risk_intensity) "
    "when pooling inputs inside `min_pool` (simultaneous 'AND' lowest-intensity rules) or `max_pool` (escalation 'OR' highest-intensity rules). "
    "NEVER pass raw integer state indices directly into `min_pool` or `max_pool`.\n"
    "   - Do NOT wrap `min_pool` or `max_pool` in artificial boolean `ite` guards when the policy specifies continuous pooling and threshold cutoffs.\n"
    "4. EXHAUSTIVE STATE REACHABILITY & HIERARCHICAL PRECEDENCE:\n"
    "   - Every discrete state `0..max_bound` MUST be reachable under Z3 verification.\n"
    "   - For action directives (final outputs), evaluate intermediate risk scores and arbiters directly according to policy decision rules.\n"
    "5. Provide 1 to 3 concrete `test_cases` whose `input_assignments` are satisfiable under upstream DAG constraints."
)


def format_cegar_repair_prompt(diagnostics: list[str]) -> str:
    """Formats verification counterexample feedback for CEGAR repair."""
    bullet_points = "\n".join(f"- {msg}" for msg in diagnostics)
    return (
        "\n\n=== Z3 FORMAL VERIFIER COUNTEREXAMPLE / ERROR FEEDBACK ===\n"
        "Your previous AST failed formal verification in Z3 with the following diagnostics:\n"
        f"{bullet_points}\n"
        "Fix the `expr_ast` (and `continuous_intensity_ast` / `test_cases` if needed) so all Z3 sort, "
        "exhaustive state/regime reachability, bound, and test case checks pass."
    )
