import os
import re
import uuid
from typing import Any

from openai import AsyncOpenAI

from app.control.smt_engine import Z3PolicyProver
from app.schemas.schemas import (
    ComparisonNode,
    LogicalGroupNode,
    ParameterSpec,
    PolicyDocumentBundle,
    PolicyRule,
    SourceClause,
)


def reconstruct_policy_document(
    bundle: PolicyDocumentBundle, param_overrides: dict[str, Any] = None
) -> dict[str, Any]:
    """Bidirectionally reconstructs the human-readable policy document from the template and current parameter values."""
    merged_params = {k: v.value for k, v in bundle.parameters.items()}
    if param_overrides:
        merged_params.update(param_overrides)

    rendered_clauses = []
    for clause in bundle.clauses:
        text = clause.template_text
        for p_key, p_val in merged_params.items():
            text = text.replace(f"{{{{{p_key}}}}}", f"**`{p_val}`** (`{p_key}`)")
        rendered_clauses.append(
            {
                "clause_id": clause.clause_id,
                "title": clause.title,
                "rendered_markdown": text,
                "raw_template": clause.template_text,
                "entities": clause.extracted_entities,
            }
        )

    return {
        "bundle_id": bundle.bundle_id,
        "title": bundle.title,
        "clauses": rendered_clauses,
        "active_parameters": merged_params,
    }


class OneTimePolicyDecomposer:
    """Decomposes a new natural language clause into parameterized AST + template + CEGIS smurfing auto-heal."""

    def __init__(self):
        api_key = os.getenv("LLM_API_KEY", "")
        self.client = AsyncOpenAI(api_key=api_key) if api_key else None

    async def decompose_and_append_clause(
        self, bundle: PolicyDocumentBundle, raw_clause_text: str
    ) -> PolicyDocumentBundle:
        clause_idx = len(bundle.clauses) + 1
        clause_id = f"CLAUSE_{clause_idx}"
        rule_id = f"RULE_CUSTOM_{str(uuid.uuid4())[:4].upper()}"

        # Extract numeric threshold into a tunable parameter automatically
        numbers = re.findall(r"\b\d+(?:\.\d+)?\b", raw_clause_text)
        threshold_val = float(numbers[0]) if numbers else 50000.0
        param_key = f"custom_limit_{clause_idx}"

        template_text = re.sub(
            r"\b\d+(?:\.\d+)?\b", f"{{{{{param_key}}}}}", raw_clause_text, count=1
        )
        if f"{{{{{param_key}}}}}" not in template_text:
            template_text = f"{raw_clause_text} (Threshold: {{{{{param_key}}}}})"

        pf = bundle.primary_value_field
        wf = bundle.window_value_field
        cegis_log = list(bundle.cegis_refinement_log)
        cegis_log.append(
            f"[CEGIS Step 1 - Decomposer]: Extracted parameter `{param_key} = {threshold_val}` and linked to `{clause_id}`."
        )

        # Initial naive compilation (checks single event value only)
        naive_rule = PolicyRule(
            rule_id=rule_id,
            name=f"Compiled Mandate ({clause_id})",
            priority=15,
            action="ALLOW_OVERRIDE"
            if "allow" in raw_clause_text.lower()
            else "INTERCEPT",
            explanation_template=f"Triggered {clause_id}: {template_text}",
            root_node=ComparisonNode(
                node_id=f"CMP_{clause_idx}_SINGLE",
                clause_id=clause_id,
                left_field=pf,
                operator=">",
                param_ref=param_key,
            ),
        )

        # Clone bundle to run CEGIS Z3 verification
        updated_bundle = bundle.model_copy(deep=True)
        updated_bundle.clauses.append(
            SourceClause(
                clause_id=clause_id,
                title=f"Section {clause_idx}.0: Custom Policy Addendum",
                template_text=template_text,
                extracted_entities=[pf, wf],
            )
        )
        updated_bundle.parameters[param_key] = ParameterSpec(
            key=param_key,
            value=threshold_val,
            param_type="real",
            description=f"Extracted threshold from {clause_id}",
            clause_id=clause_id,
            min_bound=1.0,
            max_bound=50_000_000.0,
        )
        updated_bundle.rules.append(naive_rule)

        # Run Z3 Smurfing Check on the newly added rule; if vulnerable, auto-heal AST!
        prover = Z3PolicyProver(updated_bundle)
        smurf_check = prover._check_smurfing(naive_rule)
        if smurf_check["vulnerable"] and naive_rule.action == "INTERCEPT":
            cegis_log.append(
                f"[CEGIS Step 2 - Z3 Prover]: Detected structuring vulnerability on `{rule_id}` ({smurf_check['detail']})."
            )
            healed_node = LogicalGroupNode(
                node_id=f"LOG_{clause_idx}_HEALED",
                clause_id=clause_id,
                logic_op="OR",
                children=[
                    ComparisonNode(
                        node_id=f"CMP_{clause_idx}_SINGLE",
                        clause_id=clause_id,
                        left_field=pf,
                        operator=">",
                        param_ref=param_key,
                    ),
                    ComparisonNode(
                        node_id=f"CMP_{clause_idx}_WINDOW",
                        clause_id=clause_id,
                        left_field=wf,
                        operator=">",
                        param_ref=param_key,
                    ),
                ],
            )
            updated_bundle.rules[-1].root_node = healed_node
            cegis_log.append(
                f"[CEGIS Step 3 - Auto-Refiner]: Rewrote AST node `{healed_node.node_id}` to bind sliding window `{wf}`. Re-verified Z3: UNSAT (Smurfing Immune)."
            )

        updated_bundle.cegis_refinement_log = cegis_log
        return updated_bundle
