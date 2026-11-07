import random
import uuid
from typing import Any

from app.schemas.schemas import (
    ComparisonNode,
    DomainAxiom,
    LogicalGroupNode,
    ParameterSpec,
    PolicyDocumentBundle,
    PolicyItem,
)


def get_default_bundles() -> dict[str, PolicyDocumentBundle]:
    return {
        "quant_risk": PolicyDocumentBundle(
            bundle_id="bnd_quant_v2",
            domain_key="quant_risk",
            title="Pre-Trade Algorithmic Execution & Market Impact Mandate",
            entity_key="symbol",
            primary_value_field="notional_usd",
            window_value_field="rolling_5m_notional_usd",
            fields={
                "symbol": "string",
                "notional_usd": "real",
                "rolling_5m_notional_usd": "real",
                "intraday_drawdown_pct": "real",
                "spread_bps": "real",
                "is_hedging_order": "bool",
            },
            axioms=[
                DomainAxiom(
                    axiom_id="AX_Q1",
                    description="Order notional ($1 to $50M)",
                    field="notional_usd",
                    min_val=1.0,
                    max_val=50_000_000.0,
                ),
                DomainAxiom(
                    axiom_id="AX_Q2",
                    description="5m rolling notional >= single order notional",
                    field="rolling_5m_notional_usd",
                    min_val=1.0,
                    max_val=100_000_000.0,
                    window_accumulates_field="notional_usd",
                ),
                DomainAxiom(
                    axiom_id="AX_Q3",
                    description="Intraday drawdown (0% to 100%)",
                    field="intraday_drawdown_pct",
                    min_val=0.0,
                    max_val=100.0,
                ),
                DomainAxiom(
                    axiom_id="AX_Q4",
                    description="Bid-ask spread (0.1 to 500 bps)",
                    field="spread_bps",
                    min_val=0.1,
                    max_val=500.0,
                ),
            ],
            parameters={
                "max_single_notional_usd": ParameterSpec(
                    key="max_single_notional_usd",
                    value=250000.0,
                    param_type="real",
                    description="Single order notional limit (USD)",
                    policy_id="POL_SLIPPAGE",
                    min_bound=10000.0,
                    max_bound=10000000.0,
                ),
                "max_rolling_5m_usd": ParameterSpec(
                    key="max_rolling_5m_usd",  # gitleaks:allow
                    value=500000.0,
                    param_type="real",
                    description="5m rolling notional limit (USD)",
                    policy_id="POL_SLIPPAGE",
                    min_bound=20000.0,
                    max_bound=20000000.0,
                ),
                "max_spread_bps": ParameterSpec(
                    key="max_spread_bps",
                    value=14.0,
                    param_type="real",
                    description="Spread threshold (bps)",
                    policy_id="POL_SLIPPAGE",
                    min_bound=1.0,
                    max_bound=200.0,
                ),
                "max_drawdown_pct": ParameterSpec(
                    key="max_drawdown_pct",
                    value=2.2,
                    param_type="real",
                    description="Portfolio drawdown kill-switch (%)",
                    policy_id="POL_DRAWDOWN",
                    min_bound=0.2,
                    max_bound=25.0,
                ),
                "exempt_hedging_flag": ParameterSpec(
                    key="exempt_hedging_flag",
                    value=False,
                    param_type="bool",
                    description="Non-hedging status required for kill-switch",
                    policy_id="POL_DRAWDOWN",
                ),
            },
            policies=[
                PolicyItem(
                    policy_id="POL_SLIPPAGE",
                    name="Liquidity & Anti-Smurfing Impact Guard",
                    enabled=True,
                    priority=20,
                    action="INTERCEPT",
                    natural_language_text="Intercept any order where notional_usd exceeds 250000 or rolling_5m_notional_usd exceeds 500000 while spread_bps is greater than 14.0.",
                    template_text="Intercept any order where notional_usd exceeds {{max_single_notional_usd}} or rolling_5m_notional_usd exceeds {{max_rolling_5m_usd}} while spread_bps is greater than {{max_spread_bps}}.",
                    extracted_entities=[
                        "notional_usd",
                        "rolling_5m_notional_usd",
                        "spread_bps",
                    ],
                    cegis_log=[
                        "Verified anti-structuring OR-branch linking `notional_usd` and `rolling_5m_notional_usd`."
                    ],
                    root_node=LogicalGroupNode(
                        node_id="LOG_SLIP_ROOT",
                        policy_id="POL_SLIPPAGE",
                        logic_op="AND",
                        children=[
                            LogicalGroupNode(
                                node_id="LOG_SLIP_OR",
                                policy_id="POL_SLIPPAGE",
                                logic_op="OR",
                                children=[
                                    ComparisonNode(
                                        node_id="CMP_NOTIONAL",
                                        policy_id="POL_SLIPPAGE",
                                        left_field="notional_usd",
                                        operator=">",
                                        param_ref="max_single_notional_usd",
                                    ),
                                    ComparisonNode(
                                        node_id="CMP_WIN_NOTIONAL",
                                        policy_id="POL_SLIPPAGE",
                                        left_field="rolling_5m_notional_usd",
                                        operator=">",
                                        param_ref="max_rolling_5m_usd",
                                    ),
                                ],
                            ),
                            ComparisonNode(
                                node_id="CMP_SPREAD",
                                policy_id="POL_SLIPPAGE",
                                left_field="spread_bps",
                                operator=">",
                                param_ref="max_spread_bps",
                            ),
                        ],
                    ),
                ),
                PolicyItem(
                    policy_id="POL_DRAWDOWN",
                    name="Intraday Drawdown Circuit Breaker",
                    enabled=True,
                    priority=10,
                    action="INTERCEPT",
                    natural_language_text="Intercept orders when intraday_drawdown_pct exceeds 2.2 and is_hedging_order is False.",
                    template_text="Intercept orders when intraday_drawdown_pct exceeds {{max_drawdown_pct}} and is_hedging_order is {{exempt_hedging_flag}}.",
                    extracted_entities=["intraday_drawdown_pct", "is_hedging_order"],
                    cegis_log=[
                        "Proven satisfiable and non-contradictory with POL_SLIPPAGE."
                    ],
                    root_node=LogicalGroupNode(
                        node_id="LOG_DD_ROOT",
                        policy_id="POL_DRAWDOWN",
                        logic_op="AND",
                        children=[
                            ComparisonNode(
                                node_id="CMP_DD",
                                policy_id="POL_DRAWDOWN",
                                left_field="intraday_drawdown_pct",
                                operator=">",
                                param_ref="max_drawdown_pct",
                            ),
                            ComparisonNode(
                                node_id="CMP_HEDGE",
                                policy_id="POL_DRAWDOWN",
                                left_field="is_hedging_order",
                                operator="==",
                                param_ref="exempt_hedging_flag",
                            ),
                        ],
                    ),
                ),
            ],
        ),
        "fintech_aml": PolicyDocumentBundle(
            bundle_id="bnd_aml_v2",
            domain_key="fintech_aml",
            title="FCA/PRA Real-Time Wire & Anti-Structuring Governance",
            entity_key="sender_account",
            primary_value_field="amount_gbp",
            window_value_field="rolling_24h_outflow_gbp",
            fields={
                "sender_account": "string",
                "amount_gbp": "real",
                "rolling_24h_outflow_gbp": "real",
                "risk_score": "real",
                "account_age_days": "int",
                "is_biometric_verified": "bool",
            },
            axioms=[
                DomainAxiom(
                    axiom_id="AX_A1",
                    description="Wire amount (£1 to £10M)",
                    field="amount_gbp",
                    min_val=1.0,
                    max_val=10_000_000.0,
                ),
                DomainAxiom(
                    axiom_id="AX_A2",
                    description="24h outflow >= single wire amount",
                    field="rolling_24h_outflow_gbp",
                    min_val=1.0,
                    max_val=20_000_000.0,
                    window_accumulates_field="amount_gbp",
                ),
                DomainAxiom(
                    axiom_id="AX_A3",
                    description="Risk score (0.0 to 1.0)",
                    field="risk_score",
                    min_val=0.0,
                    max_val=1.0,
                ),
                DomainAxiom(
                    axiom_id="AX_A4",
                    description="Account age (0 to 10000 days)",
                    field="account_age_days",
                    min_val=0.0,
                    max_val=10000.0,
                ),
            ],
            parameters={
                "max_single_wire_gbp": ParameterSpec(
                    key="max_single_wire_gbp",
                    value=50000.0,
                    param_type="real",
                    description="Single wire limit without biometrics (GBP)",
                    policy_id="POL_AML_WIRE",
                    min_bound=1000.0,
                    max_bound=1000000.0,
                ),
                "max_24h_outflow_gbp": ParameterSpec(
                    key="max_24h_outflow_gbp",
                    value=85000.0,
                    param_type="real",
                    description="24h cumulative outflow limit (GBP)",
                    policy_id="POL_AML_WIRE",
                    min_bound=5000.0,
                    max_bound=2000000.0,
                ),
                "unverified_biometric_flag": ParameterSpec(
                    key="unverified_biometric_flag",
                    value=False,
                    param_type="bool",
                    description="Biometric verification state matched",
                    policy_id="POL_AML_WIRE",
                ),
                "high_risk_cutoff": ParameterSpec(
                    key="high_risk_cutoff",
                    value=0.82,
                    param_type="real",
                    description="Anomaly risk score cutoff",
                    policy_id="POL_AML_MATURITY",
                    min_bound=0.1,
                    max_bound=0.99,
                ),
                "min_account_age_days": ParameterSpec(
                    key="min_account_age_days",
                    value=30,
                    param_type="int",
                    description="Minimum account age (days)",
                    policy_id="POL_AML_MATURITY",
                    min_bound=1,
                    max_bound=365,
                ),
            },
            policies=[
                PolicyItem(
                    policy_id="POL_AML_WIRE",
                    name="High-Value & Structuring Outflow Guard",
                    enabled=True,
                    priority=20,
                    action="INTERCEPT",
                    natural_language_text="Intercept transfer if amount_gbp exceeds 50000 or rolling_24h_outflow_gbp exceeds 85000 while is_biometric_verified is False.",
                    template_text="Intercept transfer if amount_gbp exceeds {{max_single_wire_gbp}} or rolling_24h_outflow_gbp exceeds {{max_24h_outflow_gbp}} while is_biometric_verified is {{unverified_biometric_flag}}.",
                    extracted_entities=[
                        "amount_gbp",
                        "rolling_24h_outflow_gbp",
                        "is_biometric_verified",
                    ],
                    cegis_log=[
                        "Protected against 2-step smurfing via `rolling_24h_outflow_gbp`."
                    ],
                    root_node=LogicalGroupNode(
                        node_id="LOG_AML_ROOT",
                        policy_id="POL_AML_WIRE",
                        logic_op="AND",
                        children=[
                            LogicalGroupNode(
                                node_id="LOG_AML_OR",
                                policy_id="POL_AML_WIRE",
                                logic_op="OR",
                                children=[
                                    ComparisonNode(
                                        node_id="CMP_AMT",
                                        policy_id="POL_AML_WIRE",
                                        left_field="amount_gbp",
                                        operator=">",
                                        param_ref="max_single_wire_gbp",
                                    ),
                                    ComparisonNode(
                                        node_id="CMP_24H",
                                        policy_id="POL_AML_WIRE",
                                        left_field="rolling_24h_outflow_gbp",
                                        operator=">",
                                        param_ref="max_24h_outflow_gbp",
                                    ),
                                ],
                            ),
                            ComparisonNode(
                                node_id="CMP_BIO",
                                policy_id="POL_AML_WIRE",
                                left_field="is_biometric_verified",
                                operator="==",
                                param_ref="unverified_biometric_flag",
                            ),
                        ],
                    ),
                ),
                PolicyItem(
                    policy_id="POL_AML_MATURITY",
                    name="New Account Anomaly Gate",
                    enabled=True,
                    priority=10,
                    action="INTERCEPT",
                    natural_language_text="Intercept transfer when risk_score exceeds 0.82 and account_age_days is less than 30.",
                    template_text="Intercept transfer when risk_score exceeds {{high_risk_cutoff}} and account_age_days is less than {{min_account_age_days}}.",
                    extracted_entities=["risk_score", "account_age_days"],
                    cegis_log=[
                        "Verified axiom boundaries on risk_score and account_age_days."
                    ],
                    root_node=LogicalGroupNode(
                        node_id="LOG_MAT_ROOT",
                        policy_id="POL_AML_MATURITY",
                        logic_op="AND",
                        children=[
                            ComparisonNode(
                                node_id="CMP_RISK",
                                policy_id="POL_AML_MATURITY",
                                left_field="risk_score",
                                operator=">",
                                param_ref="high_risk_cutoff",
                            ),
                            ComparisonNode(
                                node_id="CMP_AGE",
                                policy_id="POL_AML_MATURITY",
                                left_field="account_age_days",
                                operator="<",
                                param_ref="min_account_age_days",
                            ),
                        ],
                    ),
                ),
            ],
        ),
    }


def generate_domain_event(domain_key: str) -> dict[str, Any]:
    ev_id = f"ev_{str(uuid.uuid4())[:8]}"
    is_attack = random.random() < 0.16

    if domain_key == "quant_risk":
        notional = round(
            random.uniform(255000, 620000)
            if is_attack
            else random.expovariate(1 / 75000) + 5000,
            2,
        )
        spread = round(
            random.uniform(14.5, 26.0) if is_attack else random.uniform(1.5, 15.5), 2
        )
        dd = round(
            random.uniform(2.25, 3.8)
            if (is_attack and random.random() < 0.45)
            else random.uniform(0.1, 2.1),
            2,
        )
        return {
            "event_id": ev_id,
            "symbol": random.choice(["NVDA", "AAPL", "MSFT", "BARC.L", "AZN.L"]),
            "notional_usd": notional,
            "rolling_5m_notional_usd": notional,
            "intraday_drawdown_pct": dd,
            "spread_bps": spread,
            "is_hedging_order": False if is_attack else random.choice([True, False]),
            "_is_anomalous_attack": is_attack,
        }
    else:
        amt = round(
            random.uniform(52000, 110000)
            if is_attack
            else random.expovariate(1 / 14000) + 250,
            2,
        )
        risk = round(
            random.uniform(0.84, 0.99) if is_attack else random.uniform(0.02, 0.80), 2
        )
        age = random.randint(2, 26) if is_attack else random.randint(15, 1800)
        return {
            "event_id": ev_id,
            "sender_account": f"acct_{random.randint(100, 130)}",
            "amount_gbp": amt,
            "rolling_24h_outflow_gbp": amt,
            "risk_score": risk,
            "account_age_days": age,
            "is_biometric_verified": False
            if is_attack
            else random.choice([True, False]),
            "_is_anomalous_attack": is_attack,
        }
