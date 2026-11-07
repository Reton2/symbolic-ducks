# Global Algorithmic Execution & Quantitative Risk Policy Mandate

**Document Reference:** AMM-QRM-2026-V5
**Effective Date:** Active Trading Operations
**Governance Scope:** Global Automated Market Making, Systematic Alpha Strategies, High-Frequency Order Routing, and Electronic Liquidity Provision
**Regulatory Alignment:** SEC Rule 15c3-5 (Market Access Rule), MiFID II RTS 6 / RTS 25, FINRA Rule 3110, and Reg AT

---

## 1. Executive Summary & Regulatory Purpose

This Policy Mandate establishes the mandatory pre-trade risk controls, algorithmic gatekeepers, and real-time supervisory protocols governing all automated trading systems operating on firm infrastructure.

The mandate replaces simplistic binary kill-switches with a unified, multi-tiered risk architecture. The system continuously ingests market telemetry across continuous numerical measurements, discrete ordinal severity ratings, and categorical operational states. These telemetry streams pass through a five-stage hierarchical decision graph to govern three definitive trading directives:
1. **Block Trade Order Allocation**: A continuous numerical percentage governing the proportion of capital permissible for immediate market execution.
2. **Portfolio Liquidation Protocol**: An ordinal severity tier establishing the escalation level for unwinding inventory and cutting exposure.
3. **Master Algorithmic Operating Directive**: A categorical governance state dictating whether strategies maintain unrestricted execution, restrict flow to passive liquidity, or trigger an immediate, firm-wide trading halt.

---

## 2. Foundational Telemetry & Surveillance Indicators

The firm's risk monitoring framework continuously tracks thirty-five independent primary indicators categorized across market microstructure, volatility and pricing, technical infrastructure, and regulatory compliance.

### 2.1 Market Microstructure & Liquidity Health
* **Consolidated Book Depth**: A numerical measurement tracking the total dollar value of committed liquidity within five basis points of the inside market. Deep liquidity provides buffer against market impact, whereas drying depth signals acute structural fragility.
* **Top-of-Book Imbalance Ratio**: A continuous numerical ratio comparing available bid volume against ask volume at the national best bid and offer. Skewed ratios reveal one-sided order flow and imminent price velocity.
* **Composite Market Liquidity Stress**: An ordinal tier ranking market-wide liquidity conditions across five discrete stages: calm, normal, elevated, stressed, or crisis. This rating captures aggregate depth withdrawal across correlated market centers.
* **Quoted Bid-Ask Spread**: A numerical metric tracking the inside market spread in basis points. Spreads widening beyond historical norms indicate heightened market-maker compensation demands and severe liquidity friction.
* **Dark ATS Midpoint Divergence**: A numerical measurement of the price drift in basis points between off-exchange alternative trading system midpoint prints and the public exchange best bid/offer. Severe divergence denotes dark pool price dislocation.

### 2.2 Volatility, Momentum & Price Formation
* **Real-Time Market Volatility Index (VIX)**: A continuous numerical benchmark measuring aggregate market implied volatility in index points. Elevated levels indicate broad systemic uncertainty.
* **One-Minute Broad Market Return**: A continuous numerical percentage tracking immediate market price velocity. Rapid drops signify potential flash crash events.
* **Volume-Weighted Average Price (VWAP) Execution Drift**: A numerical metric measuring the basis-point slippage between realized fills and the daily volume-weighted average price curve.
* **Fourteen-Period Relative Strength Momentum Index**: A numerical technical indicator oscillating between zero and one hundred. Values depressing into extreme territory denote severe momentum depletion and mean-reversion risk.
* **Overnight Opening Price Gap**: An ordinal tier categorizing the magnitude of price dislocation between the previous market close and the opening cross into flat, moderate, or extreme gap regimes.
* **Options Market Maker Gamma Exposure**: An ordinal tier evaluating dealer gamma positioning across nearby option strikes into neutral, moderate, or acute squeeze states. Acute imbalances expose underlying equities to violent hedging spirals.
* **Sector Benchmark Correlation**: A continuous numerical correlation coefficient measuring the rolling thirty-minute co-movement between proprietary execution assets and lead index exchange-traded funds. A breakdown in correlation signifies idiosyncratic structural decoupling.
* **Predictive Signal Alpha Score**: A numerical standardized statistical score measuring the expected predictive value of active quantitative trading alphas. Depressed or negative scores reveal decaying quantitative edge.

### 2.3 Technical Infrastructure, Latency & Data Integrity
* **Order Round-Trip Gateway Latency**: An ordinal tier categorizing network processing delay into ultra-low, nominal, spike warning, or critical latency conditions.
* **Financial Information eXchange (FIX) Session Connection State**: A categorical status defining gateway connectivity as established and online, degraded due to missing heartbeats, or completely dropped.
* **Colocation Electrical Power Bus Status**: A categorical operational state classifying data center facility power into dual mains utility feeds online, uninterruptible generator backup engaged, or total electrical power failure.
* **Market Data Feed Heartbeat Health**: A categorical assessment of exchange feed integrity, distinguishing between realtime synchronization, packet sequence gaps, or dropped feeds with stale data.
* **API Throttling Capacity Stage**: An ordinal rating monitoring broker and gateway messaging consumption across four operational tiers: green, yellow burst, orange throttled, and red rate limit.
* **Inbound Quote Message Rate**: A discrete numerical counter tracking the volume of quote updates processed per second. Pathological message volumes denote potential quote-stuffing or gateway saturation.
* **Execution Order Loop Recursion**: A categorical operational state monitoring algorithmic child-order dispatch to identify nominal execution, rapid retries, or runaway infinite execution loops.

### 2.4 Capital Adequacy, Prime Brokerage & Market Conduct
* **Intraday Strategy Equity Drawdown**: A continuous numerical percentage tracking peak-to-trough capital erosion against allocated desk risk limits.
* **Broker Maintenance Margin Deficit**: An ordinal severity tier classifying margin adequacy across adequate capitalization, maintenance margin warning, or formal margin call deficit.
* **Desk Net Inventory Risk Position**: An ordinal tier categorizing firm inventory holdings into compliant levels within limits, thresholds approaching maximum capacity, or hard limit breaches.
* **Prime Broker Locate Availability**: A categorical status reflecting the availability of borrowable shares for short positions, classified into locate confirmed, pre-borrow restrictions, or locate failed.
* **Short-Sale Regulatory Restriction Mode**: A categorical regulatory flag identifying whether an instrument is unrestricted, subject to the SEC Rule 201 alternative uptick circuit breaker, or subject to a mandatory borrow ban.
* **Exchange Volatility Pause Stage**: An ordinal stage tracking Limit-Up/Limit-Down regulatory auction mechanisms, ranging from normal trading, through price band warnings, to formal volatility pauses and full trading halts.
* **Market-Wide Circuit Breaker Level**: An ordinal regulatory rating capturing exchange-wide trading halts triggered by S&P 500 declines across level one (seven percent), level two (thirteen percent), and level three (twenty percent) thresholds.
* **Order Size Relative to Average Daily Volume**: A numerical percentage measuring proposed single-order size against the thirty-day historical average daily volume to prevent outsized market impact and fat-finger errors.
* **Realized Execution Slippage**: A numerical metric tracking the basis-point divergence between order arrival price and final executed fill price.
* **Sub-Penny Rule Minimum Price Variation Compliance**: A categorical regulatory state tracking adherence to pricing increments, categorized as compliant, sub-penny warning, or minimum price variation violation.
* **Self-Matching and Wash Trade Monitor**: A categorical surveillance state indicating whether internal execution crossings are clear, flagged for suspicious matching patterns, or in direct violation of wash trade prohibitions.
* **Order Cancellation-to-Fill Ratio**: An ordinal risk tier monitoring quoting behavior across low, guarded, elevated, and severe tiers to intercept potential spoofing or abusive quoting strategies.
* **News and Social Media Sentiment Momentum**: A continuous numerical standardized z-score tracking sentiment velocity and unexpected negative buzz across public media feeds.
* **Trading Session Schedule Phase**: A categorical timeline marker indicating whether current operations reside in pre-market access, core trading hours, the market-closing cross, or post-close settlement.
* **Master Emergency Kill Switch Readiness**: A categorical administrative authorization state classifying desk controls into disarmed, risk administrator standby, or automated emergency trigger engaged.

---

## 3. Primary Analytical Risk Gateways

The thirty-five primary surveillance indicators are synthesized at the first analytical layer into eleven specialized gateway evaluations. Each gateway isolates a distinct dimension of operational or market risk.

### Gateway 1: Execution Latency & VWAP Quality Score
This continuous numerical score evaluates trade execution efficiency. A high score requires that the market is free from exchange volatility halts, the financial information exchange gateway maintains an active, fully connected online state, the momentum indicator confirms price stability rather than sharp depletion, and execution drift from the volume-weighted average price remains tightly bounded.

### Gateway 2: Microstructure Imbalance Tier
This ordinal tier aggregates adverse market microstructure imbalances. An elevated risk tier is triggered if the order book imbalance ratio skews away from balanced thresholds, dark pool midpoint divergence widens beyond tolerance, realized execution slippage hits extreme levels, or the algorithm exhibits rapid runaway loop retries.

### Gateway 3: Flow Toxicity & Wash Trade Risk Index
This continuous numerical metric captures predatory flow characteristics. It combines elevated market-wide liquidity stress, active warnings from the internal wash trade detector, and quoted bid-ask spreads that have contracted into aggressive, tight ranges indicative of latency-arbitrage exploitation.

### Gateway 4: Pre-Trade Order Validation Status
A categorical gateway classifying proposed orders into valid, suspicious, or rejected. Rejection occurs when a proposed order represents an abnormally large percentage of average daily volume, broad regulatory market-wide circuit breakers remain inactive (preventing natural pauses), and news sentiment momentum exhibits an acute, volatile spike.

### Gateway 5: Gateway Throttle & Risk Alarm Tier
An ordinal tier escalating system defenses whenever the cancellation-to-fill spoofing risk tier escalates, administrative kill switch authority has been actively armed by desk risk officers, the API gateway has entered severe throttling stages, or realized order slippage reaches extreme levels.

### Gateway 6: Capital Drawdown & Depth Depletion Metric
A continuous numerical indicator reflecting combined capital and liquidity degradation. It activates when available book depth within five basis points dries up severely, intraday strategy drawdown reaches or breaches established risk limits, and net desk inventory has not yet breached hard caps (indicating active, capital-exposed positions).

### Gateway 7: Volatility & Tick Discrepancy Surge Factor
A continuous numerical metric reflecting market-wide turbulence. It compounds high real-time volatility index levels, active minimum price variation tick discrepancies, and severe overnight opening price gaps, provided the gateway connection has not failed completely.

### Gateway 8: Correlation Breakdown & Alpha Decay Tier
An ordinal rating evaluating quantitative statistical failure. It escalates when correlation against the market benchmark decouples, predictive alpha signals deteriorate into negative territory, or broker margin utilization breaches maintenance thresholds.

### Gateway 9: Infrastructure & Borrow Availability Health Mode
A categorical infrastructure monitor determining whether hardware and stock borrowing conditions are nominal, degraded, or in critical failure. A critical failure regime is declared if prime broker short locates fail, colocation power suffers a total facility loss, mandatory short-sale borrowing restrictions are imposed, or extreme overnight gaps disrupt asset transfer.

### Gateway 10: Market Dislocation & Gamma Pressure Index
A continuous numerical metric tracking systemic market dislocations. It evaluates quote feed data unreliability, acute options market maker gamma squeeze tiers, or rapid one-minute market return collapse indicative of flash crashes.

### Gateway 11: Feed Message Congestion Tier
An ordinal severity rating tracking quote stream saturation. The tier escalates when inbound market quote updates reach peak messaging thresholds, order round-trip gateway latency avoids low ranges, or trading operations enter the critical closing cross phase of the session.

---

## 4. Intermediate Risk Synthesis & Desk Postures

At the second analytical depth, the primary gateways are synthesized into specialized operational regimes, desk postures, and composite exposure ratings.

### Regime 12: Market Access Permission Regime
A categorical regime determining institutional access permissions: unrestricted access, restricted access, or completely blocked. Access is restricted or blocked when the gateway throttle alarm tier escalates, the flow toxicity index spikes, or correlation breakdown tiers register severe stress.

### Regime 13: Execution Venue Routing Mode
A categorical routing directive selecting between direct market access, smart order routing, dark pool routing only, or complete order suspension. The routing engine suspends public flow or mandates dark execution when message feed congestion reaches saturation or correlation stability deteriorates.

### Regime 14: Cross-Asset Liquidity Shock Multiplier
A continuous numerical metric quantifying cross-asset contagion. It monitors whether infrastructure health remains free from critical failure, while compounding elevated liquidity stress tiers, deteriorating benchmark correlations, and overnight price gaps.

### Regime 15: Gateway Rate-Limiting Severity Tier
An ordinal tier regulating automated quote throttling. It enforces rate limits when the volatility and tick discrepancy factor surges, while outbound API consumption and inbound quote rates remain beneath hard saturation thresholds.

### Regime 16: News Sentiment Amplification Score
A continuous numerical score that magnifies market dislocation index values whenever real-time news sentiment velocity breaches acute statistical boundaries.

### Regime 17: Trading Desk Risk Execution Posture
A categorical risk mandate classifying firm-wide execution into aggressive, neutral, defensive, or halted postures. Defensive or halted postures are automatically enforced if the execution latency score deteriorates, emergency kill switch authority is actively armed or engaged, minimum price variation rules are violated, or API gateways face severe throttling.

### Regime 18: Liquidity Shock Vulnerability Tier
An ordinal vulnerability ranking that escalates whenever pre-trade order validation status indicates suspicious or rejected orders, or whenever composite market liquidity stress tiers escalate out of calm conditions.

### Regime 19: Portfolio Drawdown Escalation Tier
An ordinal severity tier capturing compound financial risk. It escalates when the capital drawdown metric rises, sector benchmark correlation breaks down, or the market volatility index surges into acute territory.

### Regime 20: Depth Depletion & Imbalance Pressure
A continuous numerical metric evaluating asymmetric order flow pressure. It combines elevated microstructure imbalance tiers, severe correlation breakdown tiers, negative sentiment momentum, and severe book depth drying near the inside market.

---

## 5. Strategic Risk Gateways & Operational Controls

At the third analytical depth, the intermediate regimes are filtered through institutional governance boundaries to derive operational directives.

### Control 21: Risk Firewall Gate Decision
A categorical firewall verdict governing automated flow: allow flow, throttle flow, or intercept flow. The firewall mandates flow interception whenever market access regimes are blocked, rate-limiting severity reaches maximum tiers, or market dislocation indices indicate structural breakdown.

### Control 22: Master Kill Switch Readiness Tier
An ordinal tier governing administrative emergency readiness. It advances toward engagement when portfolio drawdown escalation tiers remain bounded, liquidity shock vulnerability is contained, execution latency scores remain within normal operating parameters, and gateway risk alarms demand defensive posture.

### Control 23: Strategy Operational State
A categorical directive governing business continuity: normal operation, reduce exposure, or emergency shutdown. The policy mandates an immediate transition to exposure reduction or shutdown whenever depth depletion pressure spikes or liquidity shock vulnerability breaches risk tolerances.

### Control 24: Systemic Sentiment Cascade Indicator
A continuous numerical indicator measuring self-reinforcing market cascades. It compounds high news sentiment amplification scores, capital drawdown depletion metrics, and venue routing suspensions.

### Control 25: Order Routing Compliance Verdict
A categorical compliance verdict classifying order streams as approved, constrained, or prohibited. Prohibition is enforced when cross-asset liquidity shock multipliers spike, pre-trade order validation status rejects proposed flow, or gateway risk alarms indicate systemic infrastructure stress.

### Control 26: Position Deleveraging Threat Level
An ordinal threat ranking from safe to critical that mandates inventory unwinding. It escalates when the trading desk posture turns defensive or halted, microstructure imbalance tiers rise, and volatility surge factors indicate active market turbulence.

### Control 27: Execution Feasibility Metric
A continuous numerical score assessing whether market liquidity can support active execution without adverse selection. Feasibility is affirmed when routing modes maintain connectivity, infrastructure health avoids failure, rate-limiting tiers are relaxed, and flow toxicity indices remain subdued.

---

## 6. Executive Governance & Capacity Arbiters

At the fourth analytical depth, strategic risk controls converge into executive arbiters that dictate capacity allocations and wind-down procedures.

### Arbiter 28: Portfolio Liquidation Policy Trigger
A categorical policy trigger establishing whether the firm takes no action, executes partial deleveraging, or initiates full portfolio liquidation. Full liquidation is triggered whenever the risk firewall demands flow interception, the systemic sentiment cascade indicator spikes, or news sentiment amplification indicates unmodeled tail risk.

### Arbiter 29: Block Execution Readiness Rank
An ordinal readiness rank from unprepared to prime. Achieving prime execution readiness requires that position deleveraging threat levels remain minimal, execution feasibility metrics remain high, depth depletion pressure is absent, and the risk firewall affirms unrestricted flow.

### Arbiter 30: Composite Block Trade Capacity Score
A continuous numerical metric ranging from zero to one hundred representing the firm's instantaneous capacity to execute large-scale block transactions. High capacity requires that order routing compliance verdicts approve flow, execution feasibility scores are elevated, strategy operational states remain normal, and venue routing modes are fully active.

### Arbiter 31: Algorithmic Governance Operating State
A categorical operating state determining whether algorithms reside in active execution, standby pause, or permanent termination. The system transitions to standby or termination whenever strategy operational states demand exposure reduction or shutdown, or whenever risk firewall decisions intercept flow.

### Arbiter 32: Inventory Unwind Urgency Level
An ordinal severity tier ranging from passive to emergency. Urgency accelerates to emergency levels when master kill switch readiness tiers indicate active engagement, and trading desk postures demand defensive or halted execution.

---

## 7. Master Algorithmic Execution Directives

The final layer of the policy mandate establishes three definitive, legally binding execution directives.

| Directive | Protocol Nature | Target Output Range / States |
| :--- | :--- | :--- |
| **Directive 33: Block Order Allocation** | Continuous Numerical Protocol | Capital Allocation (0.0% – 100.0%) |
| **Directive 34: Portfolio Liquidation Urgency** | Ordinal Protocol | Unwind Severity Tiers (0, 1, 2, 3) |
| **Directive 35: Master Operating Directive** | Categorical Protocol | Governance State (Continue Trading, Suspend New Orders, Emergency Halt) |

### Directive 33: Block Trade Order Allocation (Numerical Protocol)
* **Metric Nature**: Continuous Numerical Percentage ($0.0\% \dots 100.0\%$).
* **Governance Standard**: This directive dictates the maximum allowable block trade sizing relative to total strategy purchasing power. The allocation percentage is computed as the strict conjunction (minimum) of the firm's Block Execution Readiness Rank and the Composite Block Trade Capacity Score.
* **Execution Constraint**: If either the readiness rank declines due to market imbalance or the composite capacity score drops due to routing friction, capital allocation scales down proportionally to zero, preventing market-impact penalties and adverse execution selection.

### Directive 34: Portfolio Liquidation Protocol (Ordinal Protocol)
* **Metric Nature**: Ordinal Severity Tier ($0 = \text{No Action}, 1 = \text{Soft Deleveraging}, 2 = \text{Orderly Wind-Down}, 3 = \text{Emergency Flatten}$).
* **Governance Standard**: This directive establishes the firm's inventory liquidation protocol. The operational tier is determined by taking the dominant severity (maximum) across the Portfolio Liquidation Policy Trigger, the Inventory Unwind Urgency Level, and the Position Deleveraging Threat Level.
* **Execution Constraint**:
  * Under Tier 0, normal inventory balancing applies.
  * Under Tier 1, all aggressive execution is barred, and inventory must be reduced passively via resting midpoint orders.
  * Under Tier 2, algorithms must actively cross the spread on lit venues to reduce gross notional exposure by fifty percent within fifteen minutes.
  * Under Tier 3 (Emergency Flatten), all algorithmic quoting is terminated, and execution algorithms must immediately sweep all available lit and dark book depth to liquidate all open risk positions to cash, regardless of execution slippage.

### Directive 35: Master Algorithmic Operating Directive (Categorical Protocol)
* **Metric Nature**: Categorical Governance State (Continue Trading, Suspend New Orders, Emergency Halt).
* **Governance Standard**: This directive represents the supreme administrative command governing algorithmic runtime processes. It evaluates the conjunction of the Algorithmic Governance Operating State, the Block Execution Readiness Rank, and the Composite Block Trade Capacity Score.
* **Execution Constraint**:
  * **Continue Trading**: Authorizes full autonomous execution across all lit and dark venues when all underlying gateways confirm healthy operations.
  * **Suspend New Orders**: Prevents new position origination while permitting resting passive orders to be filled or canceled; enforced during moderate infrastructure or volatility friction.
  * **Emergency Halt**: Enforces an immediate, hard suspension of all firm algorithms. All active gateway connections are commanded to cancel all open resting orders instantly, reject all inbound order requests, and revoke algorithmic trading credentials across all exchange venues.

---

## 8. Complete Decision Lineage & Supervisory Auditability

In strict compliance with regulatory audit trail standards (SEC Rule 15c3-5 and MiFID II RTS 6), every automated action must be bidirectionally traceable back to its foundational surveillance indicators.

| Layer Level | Architecture Component | Core Analytical Domain & Governance Functions |
| :--- | :--- | :--- |
| **Layer 0** | 35 Primary Surveillance Indicators | Market Microstructure, Infrastructure Health, Volatility, Capital & Compliance |
| **Layer 1** | 11 Primary Risk Gateways | Execution Quality, Flow Toxicity, Imbalance, Infrastructure & Power Health |
| **Layer 2** | 9 Intermediate Risk Regimes | Market Access, Venue Routing Modes, Contagion Multipliers, Desk Postures |
| **Layer 3** | 7 Strategic Risk Controls | Risk Firewalls, Operational Continuity States, Deleveraging Threat Levels |
| **Layer 4** | 5 Executive Capacity Arbiters | Liquidation Triggers, Readiness Ranks, Composite Block Capacity Scores |
| **Layer 5** | 3 Master Algorithmic Directives | Continuous Block Sizing %, Ordinal Liquidation Tier (0–3), Operating Directive |

1. **Audit Trace for Block Order Allocation**:
   The allocation percentage is derived directly from Block Execution Readiness and Composite Block Capacity. These arbiters maintain full causal lineage through twenty-four intermediate derived nodes, anchored in thirty-three primary telemetry inputs including order book depth, bid-ask spreads, quote arrival rates, execution loop detectors, and benchmark correlations. An order cannot execute without an end-to-end mathematical proof of capacity across this lineage.

2. **Audit Trace for Portfolio Liquidation Protocols**:
   The liquidation urgency tier evaluates twenty-four derived nodes and thirty-two primary inputs. It traces exposure back to broker margin calls, intraday drawdown breaches, exchange circuit breakers, colocation power stability, and dark pool midpoint dislocations. Any transition to emergency flattening preserves an indelible record of the specific telemetry inputs that triggered the escalation.

3. **Audit Trace for Master Algorithm Operating Directives**:
   The master operating directive synthesizes twenty-four derived nodes and thirty-three foundational indicators. It guarantees that an emergency trading halt is immediately enforced if any upstream causal path reveals infrastructure power collapse, gateway disconnection, market-wide regulatory circuit breaker halts, or runaway execution loops.

---

## 9. Regulatory Compliance & Governance Attestation

1. **Independent Verification**: All operational boundaries, relational operators, and logic thresholds defined within this mandate have been formally proven mathematically satisfiable, non-contradictory, and free from dead logic using automated theorem proving under Satisfiability Modulo Theories.
2. **Supervisory Oversight**: In accordance with institutional risk governance, this policy mandate is evaluated in real time on hardware-accelerated rule evaluation engines with sub-microsecond deterministic latency. Any structural amendment or parameter tuning requires formal risk committee approval, counterparty notification, and an automated regression proof before deployment to live production environments.
3. **Mandatory Annual Review**: This document shall be formally reviewed and recertified on an annual basis or immediately following any significant market structure or regulatory reform.
