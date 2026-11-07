import json
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
    PolicyItem,
)

FIELD_SYNONYMS = {
    "notional": "notional_usd",
    "order size": "notional_usd",
    "5m volume": "rolling_5m_notional_usd",
    "rolling 5m": "rolling_5m_notional_usd",
    "drawdown": "intraday_drawdown_pct",
    "spread": "spread_bps",
    "hedging": "is_hedging_order",
    "hedge": "is_hedging_order",
    "amount": "amount_gbp",
    "wire": "amount_gbp",
    "transfer": "amount_gbp",
    "24h outflow": "rolling_24h_outflow_gbp",
    "rolling 24h": "rolling_24h_outflow_gbp",
    "risk": "risk_score",
    "age": "account_age_days",
    "younger": "account_age_days",
    "biometric": "is_biometric_verified",
    "verified": "is_biometric_verified",
}


def sync_bundle_prose(bundle: PolicyDocumentBundle) -> PolicyDocumentBundle:
    """Re-renders every PolicyItem's `natural_language_text` from its `template_text` and current parameter values."""
    for pol in bundle.policies:
        rendered = pol.template_text
        for p_key, p_spec in bundle.parameters.items():
            rendered = rendered.replace(f"{{{{{p_key}}}}}", str(p_spec.value))
        pol.natural_language_text = rendered
    return bundle


class BidirectionalNLEngine:
    def __init__(self):
        api_key = os.getenv("LLM_API_KEY", "")
        base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.client = (
            AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key else None
        )
        self.model = os.getenv("LLM_MODEL", "deepseek/deepseek-v4.1-flash-1017")

    async def compile_nl_into_bundle(
        self,
        bundle: PolicyDocumentBundle,
        raw_text: str,
        policy_id: str = None,
        policy_name: str = None,
        auto_heal_smurfing: bool = True,
    ) -> PolicyDocumentBundle:
        """
        Compiles or updates a policy from natural language, extracts tunable parameters into the bundle,
        binds {{param}} placeholders for bidirectional editing, and runs CEGIS Z3 auto-healing.
        """
        updated_bundle = bundle.model_copy(deep=True)
        pid = policy_id or f"POL_{str(uuid.uuid4())[:4].upper()}"
        pname = policy_name or f"Mandate {pid}"

        # Remove old parameters belonging exclusively to this policy_id if updating in-place
        if policy_id:
            updated_bundle.parameters = {
                k: v for k, v in updated_bundle.parameters.items() if v.policy_id != pid
            }

        if self.client:
            print(raw_text)
            try:
                pol_item, new_params = await self._llm_compile(
                    updated_bundle, raw_text, pid, pname
                )
                print(pol_item, new_params)
            except Exception:
                pol_item, new_params = self._semantic_parse(
                    updated_bundle, raw_text, pid, pname
                )
        else:
            pol_item, new_params = self._semantic_parse(
                updated_bundle, raw_text, pid, pname
            )

        for k, spec in new_params.items():
            updated_bundle.parameters[k] = spec

        # Replace or append PolicyItem
        replaced = False
        for idx, existing in enumerate(updated_bundle.policies):
            if existing.policy_id == pid:
                updated_bundle.policies[idx] = pol_item
                replaced = True
                break
        if not replaced:
            updated_bundle.policies.append(pol_item)

        # CEGIS Step: Run Z3 Smurfing Check and Auto-Heal if needed
        if auto_heal_smurfing and pol_item.action == "INTERCEPT":
            prover = Z3PolicyProver(updated_bundle)
            smurf = prover._check_smurfing(pol_item)
            if smurf["vulnerable"]:
                pf = updated_bundle.primary_value_field
                wf = updated_bundle.window_value_field
                # Find the primary value parameter ref to bind the rolling window
                primary_param = next(
                    (
                        k
                        for k, v in new_params.items()
                        if pf in k or v.param_type == "real"
                    ),
                    None,
                )
                win_param_key = f"{pid.lower()}_window_limit"
                base_val = new_params[primary_param].value if primary_param else 50000.0
                updated_bundle.parameters[win_param_key] = ParameterSpec(
                    key=win_param_key,
                    value=base_val,
                    param_type="real",
                    description=f"Auto-healed rolling window threshold ({wf})",
                    policy_id=pid,
                    min_bound=1.0,
                    max_bound=50_000_000.0,
                )
                healed_root = LogicalGroupNode(
                    node_id=f"LOG_{pid}_CEGIS",
                    policy_id=pid,
                    logic_op="OR",
                    children=[
                        pol_item.root_node,
                        ComparisonNode(
                            node_id=f"CMP_{pid}_WIN",
                            policy_id=pid,
                            left_field=wf,
                            operator=">",
                            param_ref=win_param_key,
                        ),
                    ],
                )
                pol_item.root_node = healed_root
                pol_item.template_text += (
                    f" [CEGIS Auto-Guard: or {wf} > {{{{{win_param_key}}}}}]"
                )
                if wf not in pol_item.extracted_entities:
                    pol_item.extracted_entities.append(wf)
                pol_item.cegis_log.append(
                    f"Z3 detected 2-step structuring vulnerability ({smurf['detail']}). Auto-healed AST by adding `{wf} > {{{{{win_param_key}}}}}`."
                )

        return sync_bundle_prose(updated_bundle)

    async def _llm_compile(
        self, bundle: PolicyDocumentBundle, raw_text: str, pid: str, pname: str
    ) -> tuple[PolicyItem, dict[str, ParameterSpec]]:
        sys_prompt = f"""You are a Neuro-Symbolic Policy Compiler. Translate the user's natural language policy into JSON.
ALLOWED FIELDS & TYPES: {json.dumps(bundle.fields)}
Output JSON with:
- "action": "INTERCEPT" | "ALLOW_OVERRIDE"
- "logic_op": "AND" | "OR"
- "clauses": list of {{"field": str, "operator": ">" | "<" | ">=" | "<=" | "==", "value": number | bool | str, "param_name": str}}
"""
        res = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": raw_text},
            ],
            temperature=0.0,
        )
        parsed = json.loads(res.choices[0].message.content)
        return self._build_policy_from_clauses(
            bundle,
            raw_text,
            pid,
            pname,
            parsed.get("action", "INTERCEPT"),
            parsed.get("logic_op", "AND"),
            parsed.get("clauses", []),
        )

    def _semantic_parse(
        self, bundle: PolicyDocumentBundle, raw_text: str, pid: str, pname: str
    ) -> tuple[PolicyItem, dict[str, ParameterSpec]]:
        """Deterministic multi-clause natural language compiler supporting synonyms, operators, and boolean connectors."""
        text_lower = raw_text.lower()
        action = (
            "ALLOW_OVERRIDE"
            if any(
                w in text_lower
                for w in ["allow", "permit", "pass", "approve", "override"]
            )
            else "INTERCEPT"
        )
        logic_op = "OR" if " or " in text_lower and " and " not in text_lower else "AND"

        # Split into sub-phrases by 'and', 'or', 'while', 'when', 'unless'
        segments = re.split(
            r"\b(?:and|or|while|when|unless|where)\b", raw_text, flags=re.IGNORECASE
        )
        clauses = []

        for seg in segments:
            seg_low = seg.lower()
            matched_field = None
            for f in bundle.fields:
                if f.lower() in seg_low or f.replace("_", " ").lower() in seg_low:
                    matched_field = f
                    break
            if not matched_field:
                for syn, target_f in FIELD_SYNONYMS.items():
                    if syn in seg_low and target_f in bundle.fields:
                        matched_field = target_f
                        break
            if not matched_field:
                continue

            ftype = bundle.fields[matched_field]
            op = ">"
            if any(
                w in seg_low
                for w in ["less than", "under", "below", "younger than", "<"]
            ):
                op = "<=" if "or equal" in seg_low or "<=" in seg_low else "<"
            elif any(
                w in seg_low
                for w in ["greater than", "exceeds", "over", "above", "at least", ">"]
            ):
                op = ">=" if "at least" in seg_low or ">=" in seg_low else ">"
            elif any(
                w in seg_low
                for w in ["is false", "not verified", "unverified", "false", "=="]
            ):
                op = "=="

            if ftype == "bool":
                val = not any(
                    w in seg_low for w in ["false", "not", "unverified", "non-hedging"]
                )
                op = "=="
            elif ftype in ("real", "int"):
                nums = re.findall(r"\b\d+(?:\.\d+)?\b", seg)
                if not nums:
                    continue
                val = float(nums[-1]) if ftype == "real" else int(float(nums[-1]))
            else:
                val = "ANY"

            clauses.append(
                {
                    "field": matched_field,
                    "operator": op,
                    "value": val,
                    "param_name": f"{pid.lower()}_{matched_field}",
                }
            )

        if not clauses:
            pf = bundle.primary_value_field
            nums = re.findall(r"\b\d+(?:\.\d+)?\b", raw_text)
            val = float(nums[0]) if nums else 50000.0
            clauses.append(
                {
                    "field": pf,
                    "operator": ">",
                    "value": val,
                    "param_name": f"{pid.lower()}_{pf}",
                }
            )

        return self._build_policy_from_clauses(
            bundle, raw_text, pid, pname, action, logic_op, clauses
        )

    def _build_policy_from_clauses(
        self,
        bundle: PolicyDocumentBundle,
        raw_text: str,
        pid: str,
        pname: str,
        action: str,
        logic_op: str,
        clauses: list[dict[str, Any]],
    ) -> tuple[PolicyItem, dict[str, ParameterSpec]]:
        new_params: dict[str, ParameterSpec] = {}
        comp_nodes: list[ComparisonNode] = []
        entities: list[str] = []
        template_text = raw_text

        for idx, c in enumerate(clauses):
            field = c["field"]
            if field not in bundle.fields:
                continue
            ftype = bundle.fields[field]
            p_key = f"{pid.lower()}_{field}_{idx + 1}"
            val = c["value"]

            new_params[p_key] = ParameterSpec(
                key=p_key,
                value=val,
                param_type=ftype,
                description=f"{pname}: {field} ({c['operator']})",
                policy_id=pid,
                min_bound=0.0 if ftype in ("real", "int") else None,
                max_bound=50_000_000.0 if ftype in ("real", "int") else None,
            )
            # Replace first occurrence of literal value in template_text with {{p_key}}
            val_str = (
                str(int(val))
                if isinstance(val, float) and val.is_integer()
                else str(val)
            )
            if val_str in template_text:
                template_text = template_text.replace(val_str, f"{{{{{p_key}}}}}", 1)
            else:
                template_text += f" [{field} {c['operator']} {{{{{p_key}}}}}]"

            if field not in entities:
                entities.append(field)

            comp_nodes.append(
                ComparisonNode(
                    node_id=f"CMP_{pid}_{idx + 1}",
                    policy_id=pid,
                    left_field=field,
                    operator=c["operator"],
                    param_ref=p_key,
                )
            )

        root_node = (
            comp_nodes[0]
            if len(comp_nodes) == 1
            else LogicalGroupNode(
                node_id=f"LOG_{pid}_ROOT",
                policy_id=pid,
                logic_op=logic_op,
                children=comp_nodes,
            )
        )

        pol_item = PolicyItem(
            policy_id=pid,
            name=pname,
            enabled=True,
            priority=15,
            action=action,
            natural_language_text=raw_text,
            template_text=template_text,
            extracted_entities=entities,
            root_node=root_node,
            cegis_log=[
                f"Compiled {len(comp_nodes)} predicate(s) from natural language with bidirectional parameter bindings."
            ],
        )
        return pol_item, new_params
