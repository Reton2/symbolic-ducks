# Global Algorithmic Execution & Quantitative Risk Policy Mandate

**Document Reference:** AMM-QRM-2026-V5

**Effective Date:** Active Trading Operations

**Governance Scope:** Global Automated Market Making, Systematic Alpha Strategies, High-Frequency Order Routing, and Electronic Liquidity Provision

**Regulatory Alignment:** SEC Rule 15c3-5 (Market Access Rule), MiFID II RTS 6 / RTS 25, FINRA Rule 3110, Reg SHO, and Reg AT

## 1. Executive Summary & Desk Calculation Framework

This Policy Mandate establishes the mandatory pre-trade risk controls, quantitative gatekeepers, and real-time supervisory protocols governing all automated trading systems operating on firm infrastructure.

The mandate replaces binary kill-switches with a deterministic, five-layer risk evaluation hierarchy. To allow both automated systems and desk risk officers to evaluate risk by hand across mixed data types, all primary telemetry streams are continuously monitored across their operating bounds and translated onto a unified **0.0 to 100.0 risk-intensity scale**, where **0.0** represents zero risk friction and **100.0** represents a critical limit breach.

When desk officers evaluate conditions across this hierarchy by hand, three standard desk rules apply:

* **Inverting a Risk Score (Health vs. Stress):** When a rule checks whether an indicator is *healthy* or *free from stress* rather than breached, its health value is simply **100.0 minus its current risk intensity**.
* **Simultaneous Conditions ("And" Rules):** When a gateway or regime requires multiple conditions to hold at the same time (**and**), the resulting intensity is governed by the **lowest (most limiting) intensity** among those active inputs, and then mapped to the corresponding state or tier of the target metric.
* **Escalation Triggers ("Or" Rules):** When a gateway or regime escalates if *any* listed trigger occurs (**or**), the resulting severity is driven by the **single highest (most severe) intensity** among the triggered inputs, and then mapped to the corresponding state or tier of the target metric.
* **Standard Tier & State Alignment:** Across all ordinal tiers and categorical states, intensities step evenly across the 0.0 to 100.0 scale:
* **Three-State / Three-Tier Scales** (ordered from lowest to highest): 1st state = **0.0**, 2nd state = **50.0**, 3rd state = **100.0** (unless a specific custom weight is noted in Section 2).
* **Four-State / Four-Tier Scales**: 1st = **0.0**, 2nd = **33.33**, 3rd = **66.67**, 4th = **100.0**.
* **Five-Tier Scales**: 1st = **0.0**, 2nd = **25.0**, 3rd = **50.0**, 4th = **75.0**, 5th = **100.0**.



These thirty-five foundational streams flow through thirty-two intermediate analytical assessments to govern three binding desk execution directives:

1. **Block Trade Order Allocation**: A continuous numerical percentage (**0.0% to 100.0%**) governing the proportion of strategy purchasing power permissible for immediate block execution.
2. **Portfolio Liquidation Protocol**: A four-step ordinal escalation schedule (**No Liquidation**, **Soft Deleverage**, **Orderly Wind-Down**, and **Emergency Flatten**) for unwinding inventory and cutting gross exposure.
3. **Master Algorithmic Operating Directive**: A three-state categorical governance command (**Continue Trading**, **Suspend New Orders**, or **Emergency Halt**) dictating whether strategies maintain autonomous execution, restrict flow to passive risk reduction, or execute an immediate firm-wide halt.

## 2. Foundational Telemetry & Surveillance Indicators

The firm's risk monitoring framework tracks thirty-five independent primary indicators across market microstructure, volatility and pricing, technical infrastructure, and regulatory compliance. Each indicator operates within strict numerical bounds or ordered categories with calibrated desk thresholds.

### 2.1 Market Microstructure & Liquidity Health

* **Consolidated Book Depth**: A continuous dollar measurement (**USD**) bounded between **$0.0 and $5,000,000.0** (normal baseline: **$450,000.0**), tracking committed liquidity within 5 basis points of the national best bid and offer. Deep liquidity of **$50,000.0 or greater** carries a baseline risk intensity of **15.0**, whereas depth dropping strictly below **$50,000.0** signals acute structural fragility and assigns a maximum risk intensity of **100.0**.
* **Top-of-Book Imbalance Ratio**: A continuous ratio of `(Bid Volume − Ask Volume) / (Bid Volume + Ask Volume)` bounded between **−1.0 and +1.0** (normal baseline: **0.05**). Ratios at or below **0.65** reflect balanced two-sided flow (baseline intensity **20.0**), whereas a ratio strictly exceeding **0.65** reveals acute one-sided order flow pressure and assigns a **100.0** risk intensity.
* **Composite Market Liquidity Stress**: A five-tier ordinal rating ordered from lowest to highest across **Calm** (0.0 intensity), **Normal** (baseline, 25.0 intensity), **Elevated** (50.0 intensity), **Stressed** (75.0 intensity), and **Crisis** (100.0 intensity). Each step up adds **25.0** points of stress intensity, with **Elevated** or higher signaling material cross-venue depth withdrawal.
* **Quoted Bid-Ask Spread**: A continuous measurement in basis points (**bps**) bounded between **0.1 bps and 300.0 bps** (normal baseline: **4.2 bps**), tracking the inside market spread. A spread of **16.0 bps or wider** marks severe liquidity friction (**100.0** intensity), whereas spreads strictly tighter than **16.0 bps** (**0.1 bps to 15.99 bps**, baseline intensity **10.0**) represent contracted inside pricing that is vulnerable to toxic latency arbitrage when paired with wash-trade alerts (giving an inverted tight-spread vulnerability score of **90.0**).
* **Dark ATS Midpoint Divergence**: A continuous measurement in basis points (**bps**) bounded between **0.0 bps and 100.0 bps** (normal baseline: **2.5 bps**), tracking price drift between off-exchange alternative trading system midpoint prints and the lit exchange best bid/offer midpoint. Divergence strictly exceeding **12.0 bps** flags severe dark pool price dislocation (**100.0** intensity, versus **10.0** at or below **12.0 bps**).

### 2.2 Volatility, Momentum & Price Formation

* **Real-Time Market Volatility Index (VIX)**: A continuous benchmark in index points (**pts**) bounded between **9.0 pts and 90.0 pts** (normal baseline: **17.5 pts**), measuring aggregate 30-day implied market volatility. A VIX level of **32.0 pts or higher** declares a systemic volatility surge (**100.0** intensity, versus **15.0** strictly below **32.0 pts**).
* **One-Minute Broad Market Return**: A continuous percentage return (**%**) bounded between **−25.0% and +10.0%** (normal baseline: **+0.2%**), tracking immediate market price velocity. A return at or below **−6.0%** (a one-minute drop of 6.0% or worse) triggers an immediate flash-crash dislocation alert (**100.0** intensity, versus **10.0** strictly above **−6.0%**).
* **Volume-Weighted Average Price (VWAP) Execution Drift**: A continuous slippage metric in basis points (**bps**) bounded between **0.0 bps and 250.0 bps** (normal baseline: **4.0 bps**), measuring divergence between realized fills and the rolling daily VWAP curve. Drift strictly exceeding **18.0 bps** breaches execution quality bounds (**100.0** risk intensity, versus **15.0** when kept at or below **18.0 bps**).
* **Fourteen-Period Relative Strength Momentum Index**: A continuous technical oscillator (**index**) bounded between **0.0 and 100.0** (normal baseline: **54.0**). A reading at or below **25.0** denotes severe downward momentum depletion and mean-reversion risk (**100.0** intensity), whereas readings strictly above **25.0** confirm price stability (**20.0** baseline intensity).
* **Overnight Opening Price Gap**: A three-tier ordinal rating ordered from lowest to highest across **Flat** (baseline, **0.0** intensity), **Moderate Gap** (**50.0** intensity), and **Extreme Gap** (**100.0** intensity), classifying price dislocation between the prior market close and the opening cross.
* **Options Market Maker Gamma Exposure**: A three-tier ordinal rating ordered from lowest to highest across **Neutral** (baseline, **0.0** intensity), **Moderate Gamma** (**50.0** intensity), and **Acute Gamma Squeeze** (**100.0** intensity), evaluating aggregate dealer gamma positioning across nearby strikes.
* **Sector Benchmark Correlation**: A continuous Pearson correlation coefficient (**corr**) bounded between **−1.0 and +1.0** (normal baseline: **0.82**), measuring rolling 30-minute co-movement between proprietary execution holdings and lead sector exchange-traded funds. Correlation dropping strictly below **0.20** signifies structural decoupling and correlation breakdown (**100.0** intensity, versus **15.0** at or above **0.20**).
* **Predictive Signal Alpha Score**: A continuous standardized z-score (**z**) bounded between **−5.0 and +5.0** (normal baseline: **+1.4**), measuring the expected edge of active quantitative models. A score deteriorating to **−1.2 or lower** flags critical alpha decay (**100.0** intensity, versus **15.0** strictly above **−1.2**).

### 2.3 Technical Infrastructure, Latency & Data Integrity

* **Order Round-Trip Gateway Latency**: A four-tier ordinal rating ordered from lowest to highest across **Ultra-Low** (under 0.5 ms, **0.0** intensity), **Nominal** (baseline, **33.33** intensity), **Spike Warning** (**66.67** intensity), and **Critical Latency** (**100.0** intensity), categorizing wire-to-wire network acknowledgement delay.
* **Financial Information eXchange (FIX) Session Connection State**: A three-state categorical operational status ordered across **Connected** (baseline, active bidirectional heartbeats, **0.0** intensity), **Heartbeat Degraded** (missed heartbeats or retransmission delays, **50.0** intensity), and **Dropped** (complete session loss, **100.0** intensity).
* **Colocation Electrical Power Bus Status**: A three-state categorical facility status ordered across **Dual Mains** (baseline, redundant utility feeds online, **0.0** intensity), **Generator** (uninterruptible UPS and diesel backup engaged, **50.0** intensity), and **Total Power Loss** (dual-bus facility outage, **100.0** intensity).
* **Market Data Feed Heartbeat Health**: A three-state categorical integrity status ordered across **Realtime Synchronized** (baseline, zero packet loss, **0.0** intensity), **Sequence Gap** (UDP packet gaps undergoing replay, **50.0** intensity), and **Stale Dropped** (dropped feed or stale order book quotes, **100.0** intensity).
* **API Throttling Capacity Stage**: A four-stage ordinal rating ordered from lowest to highest across **Green** (baseline, under 50% capacity, **0.0** intensity), **Yellow Burst** (**33.33** intensity), **Orange Throttled** (active message pacing, **66.67** intensity), and **Red Rate Limit** (hard session cap saturation, **100.0** intensity), monitoring outbound gateway messaging utilization.
* **Inbound Quote Message Rate**: A discrete integer counter in messages per second (**msg/s**) bounded between **100 msg/s and 100,000 msg/s** (normal baseline: **4,500 msg/s**). A rate of **25,000 msg/s or higher** denotes pathological quote-stuffing or gateway saturation (**100.0** intensity, versus **10.0** strictly below **25,000 msg/s**).
* **Execution Order Loop Recursion**: A three-state categorical operational monitor ordered across **Nominal** (baseline, **0.0** intensity), **Rapid Retry** (elevated cancel-replace cycling, **50.0** intensity), and **Runaway Loop** (self-referential infinite order dispatch, **100.0** intensity).

### 2.4 Capital Adequacy, Prime Brokerage & Market Conduct

* **Intraday Strategy Equity Drawdown**: A continuous percentage (**%**) bounded between **0.0% and 25.0%** (normal baseline: **0.45%**), tracking intraday peak-to-trough capital erosion against desk equity. A drawdown reaching or exceeding **2.8%** breaches the desk drawdown limit (**100.0** intensity, versus **15.0** strictly below **2.8%**).
* **Broker Maintenance Margin Deficit**: A three-tier ordinal severity rating ordered from lowest to highest across **Adequate** (baseline, excess margin buffer, **0.0** intensity), **Maintenance Warning** (**50.0** intensity), and **Margin Call Deficit** (formal capital deficit, **100.0** intensity).
* **Desk Net Inventory Risk Position**: A three-tier ordinal rating ordered from lowest to highest across **Within Limits** (baseline, **0.0** intensity), **Approaching Max** (soft limit warning, **50.0** intensity), and **Limit Breached** (hard notional cap reached, **100.0** intensity).
* **Prime Broker Locate Availability**: A three-state categorical borrow status ordered across **Locate Confirmed** (baseline, **0.0** intensity), **Pre-Borrow Only** (hard-to-borrow restriction, **50.0** intensity), and **Locate Failed** (short borrow denied or recalled, **100.0** intensity).
* **Short-Sale Regulatory Restriction Mode**: A three-state categorical regulatory flag ordered across **Unrestricted** (baseline, **0.0** intensity), **Rule 201 Triggered** (SEC Alternative Uptick circuit breaker active, **60.0** intensity), and **Hard Borrow Ban** (mandatory regulatory short-sale prohibition, **100.0** intensity).
* **Exchange Volatility Pause Stage**: A four-stage ordinal rating ordered from lowest to highest across **Normal** (baseline, **0.0** intensity), **LULD Warning** (price at band boundary, **33.33** intensity), **Volatility Pause** (5-minute Limit-Up/Limit-Down auction pause, **66.67** intensity), and **Halted** (full security trading halt, **100.0** intensity).
* **Market-Wide Circuit Breaker Level**: A four-level ordinal regulatory rating ordered from lowest to highest across **None** (baseline, active trading, **0.0** intensity), **Level 1** (7% S&P 500 decline, **33.33** intensity), **Level 2** (13% decline, **66.67** intensity), and **Level 3** (20% decline, full-day market closure, **100.0** intensity).
* **Order Size Relative to Average Daily Volume**: A continuous percentage (**%**) bounded between **0.0% and 50.0%** (normal baseline: **0.8%**), measuring proposed single-order notional size against 30-day historical average daily volume. An order size of **5.0% or greater** triggers a fat-finger market-impact alert (**100.0** intensity, versus **10.0** strictly below **5.0%**).
* **Realized Execution Slippage**: A continuous metric in basis points (**bps**) bounded between **−10.0 bps** (price improvement) and **200.0 bps** (normal baseline: **3.5 bps**), tracking fill divergence against arrival midpoint. Slippage of **22.0 bps or higher** flags extreme adverse selection (**100.0** intensity, versus **10.0** strictly below **22.0 bps**).
* **Sub-Penny Rule Minimum Price Variation Compliance**: A three-state categorical regulatory status ordered across **Compliant** (baseline, **0.0** intensity), **Sub-Penny Warning** (internal tick quantization applied, **50.0** intensity), and **MPV Violation** (rejected sub-penny order increment, **100.0** intensity), tracking SEC Rule 612 pricing adherence.
* **Self-Matching and Wash Trade Monitor**: A three-state categorical surveillance status ordered across **Clear** (baseline, zero internal crosses, **0.0** intensity), **Suspicious Cross** (correlated opposite-side orders resting simultaneously, **50.0** intensity), and **Flagged Violation** (confirmed wash-trade breach, **100.0** intensity).
* **Order Cancellation-to-Fill Ratio**: A four-tier ordinal spoofing surveillance rating ordered from lowest to highest across **Low** (baseline, **0.0** intensity), **Guarded** (**33.33** intensity), **Elevated** (**66.67** intensity), and **Severe** (spoofing alert, **100.0** intensity).
* **News and Social Media Sentiment Momentum**: A continuous standardized z-score (**sigma**) bounded between **−5.0 sigma and +5.0 sigma** (normal baseline: **0.1 sigma**). A reading of **2.5 sigma or higher** marks an acute sentiment velocity shock (**100.0** intensity, versus **10.0** strictly below **2.5 sigma**).
* **Trading Session Schedule Phase**: A four-phase categorical timeline marker ordered across **Pre-Market** (**10.0** intensity), **Core Trading** (baseline, **10.0** intensity), **Closing Cross** (critical closing auction window, **100.0** intensity), and **Post-Close** (**10.0** intensity).
* **Master Emergency Kill Switch Readiness**: A three-state categorical administrative authorization status ordered across **Disarmed** (baseline, **0.0** intensity), **Risk Admin Standby** (manually armed by risk officer, **60.0** intensity), and **Auto Trigger Engaged** (emergency halt triggered, **100.0** intensity).

## 3. Layer 1: Primary Analytical Risk Gateways

At the first analytical layer, the desk synthesizes the thirty-five primary surveillance indicators into eleven specialized gateway evaluations.

### Gateway 1: Execution Latency & VWAP Quality Score

A continuous numerical health score bounded between **0.0 and 100.0** that measures overall trade execution efficiency. For this score to remain healthy, four conditions must hold at the same time: the **Exchange Volatility Pause Stage** is **Normal**, the **Financial Information eXchange (FIX) Session Connection State** is **Connected**, the **Fourteen-Period Relative Strength Momentum Index** remains strictly above **25.0**, and **Volume-Weighted Average Price (VWAP) Execution Drift** remains at or below **18.0 bps**. The desk calculates the score by taking the lowest health value (100.0 minus risk intensity) across those four inputs. When all four conditions hold, the score stays at **80.0** (capped by the 20.0 baseline intensity of the momentum index); if any single condition breaches its healthy bound, the score drops to **0.0** (or steps down proportionally if an ordinal pause or connection state degrades).

### Gateway 2: Microstructure Imbalance Tier

A five-tier ordinal rating ordered across **Balanced**, **Mild**, **Moderate**, **Acute**, and **Extreme**. It escalates whenever any of the following four microstructure problems occur: the **Top-of-Book Imbalance Ratio** strictly exceeds **0.65**, **Dark ATS Midpoint Divergence** strictly exceeds **12.0 bps**, **Realized Execution Slippage** reaches **22.0 bps or higher**, or **Execution Order Loop Recursion** enters **Rapid Retry** or **Runaway Loop**. The gateway takes the worst risk intensity among these four inputs: entering **Rapid Retry** (50.0 intensity) places the gateway at **Moderate**, while a breach of any of the three numerical thresholds or entering **Runaway Loop** (100.0 intensity) escalates the gateway to **Extreme**.

### Gateway 3: Flow Toxicity & Wash Trade Risk Index

A continuous numerical metric bounded between **0.0 and 100.0** that detects predatory internal crossing during illiquid conditions. It triggers only when three conditions are present at the same time: **Composite Market Liquidity Stress** is **Elevated**, **Stressed**, or **Crisis** (intensity 50.0 or higher), the **Self-Matching and Wash Trade Monitor** is **Suspicious Cross** or **Flagged Violation** (intensity 50.0 or higher), and the **Quoted Bid-Ask Spread** has *not* widened to 16.0 bps (remaining strictly below **16.0 bps**, which carries a 90.0 inverted tight-spread vulnerability score). The index equals the lowest intensity across these three conditions.

### Gateway 4: Pre-Trade Order Validation Status

A three-state categorical gateway ordered across **Valid**, **Suspicious**, and **Rejected**. An order is flagged when three conditions occur simultaneously: **Order Size Relative to Average Daily Volume** reaches **5.0% or greater**, the **Market-Wide Circuit Breaker Level** remains at **None** (100.0 inverted intensity, meaning no external market halt is cushioning the flow), and **News and Social Media Sentiment Momentum** reaches **2.5 sigma or higher**. Taking the lowest intensity across these three factors, the simultaneous occurrence of all three drives the status to **Rejected** (100.0 intensity).

### Gateway 5: Gateway Throttle & Risk Alarm Tier

A four-tier ordinal rating ordered across **Clear**, **Watch**, **Throttle**, and **Intercept**. It escalates if any one of four operational alarms is triggered: the **Order Cancellation-to-Fill Ratio** rises to **Guarded**, **Elevated**, or **Severe**, **Master Emergency Kill Switch Readiness** is placed in **Risk Admin Standby** or **Auto Trigger Engaged**, the **API Throttling Capacity Stage** rises to **Yellow Burst**, **Orange Throttled**, or **Red Rate Limit**, or **Realized Execution Slippage** reaches **22.0 bps or higher**. The tier is set by whichever of these four alarms carries the highest current risk intensity.

### Gateway 6: Capital Drawdown & Depth Depletion Metric

A continuous numerical indicator bounded between **0.0 and 100.0** that measures active capital-at-risk during a book liquidity vacuum. It requires three conditions to hold simultaneously: **Consolidated Book Depth** dries up strictly below **$50,000.0**, **Intraday Strategy Equity Drawdown** reaches **2.8% or higher**, and the **Desk Net Inventory Risk Position** has not yet hit a hard stop—remaining at **Within Limits** (100.0 inverted exposure score) or **Approaching Max** (50.0 inverted exposure score), indicating the desk is still actively carrying exposed inventory. The metric equals the lowest intensity across these three inputs.

### Gateway 7: Volatility & Tick Discrepancy Surge Factor

A continuous numerical metric bounded between **0.0 and 100.0** that captures pricing instability across volatile market opens while order lines remain open. It requires four simultaneous conditions: the **Real-Time Market Volatility Index (VIX)** reaches **32.0 pts or higher**, **Sub-Penny Rule Minimum Price Variation Compliance** registers a **Sub-Penny Warning** or **MPV Violation**, the **Overnight Opening Price Gap** registers a **Moderate Gap** or **Extreme Gap**, and the **Financial Information eXchange (FIX) Session Connection State** is not completely dropped—remaining either **Connected** (100.0 inverted connectivity score) or **Heartbeat Degraded** (50.0 inverted connectivity score). The factor equals the lowest intensity among these four conditions.

### Gateway 8: Correlation Breakdown & Alpha Decay Tier

A four-tier ordinal rating ordered across **Stable**, **Stressed**, **Breakdown**, and **Margin Deficit**. It escalates whenever **Sector Benchmark Correlation** drops strictly below **0.20**, **Predictive Signal Alpha Score** deteriorates to **−1.2 or lower**, or **Broker Maintenance Margin Deficit** worsens to **Maintenance Warning** or **Margin Call Deficit**. The tier is governed by the single most severe reading among those three indicators.

### Gateway 9: Infrastructure & Borrow Availability Health Mode

A three-state categorical infrastructure monitor ordered across **Nominal**, **Degraded**, and **Critical Failure**. It worsens if any of four operational or regulatory issues arise: **Prime Broker Locate Availability** degrades to **Pre-Borrow Only** or **Locate Failed**, **Colocation Electrical Power Bus Status** shifts to **Generator** or **Total Power Loss**, **Short-Sale Regulatory Restriction Mode** enters **Rule 201 Triggered** or **Hard Borrow Ban**, or the **Overnight Opening Price Gap** widens to **Moderate Gap** or **Extreme Gap**. Any intermediate warning state (**Pre-Borrow Only**, **Generator**, **Rule 201 Triggered**, or **Moderate Gap**) moves the gateway to **Degraded**, while any severe state (**Locate Failed**, **Total Power Loss**, **Hard Borrow Ban**, or **Extreme Gap**) moves it immediately to **Critical Failure**.

### Gateway 10: Market Dislocation & Gamma Pressure Index

A continuous numerical metric bounded between **0.0 and 100.0** that tracks acute structural market stress. It takes the highest risk intensity across three systemic dislocation triggers: **Market Data Feed Heartbeat Health** degrading to **Sequence Gap** (50.0) or **Stale Dropped** (100.0), **Options Market Maker Gamma Exposure** rising to **Moderate Gamma** (50.0) or **Acute Gamma Squeeze** (100.0), or the **One-Minute Broad Market Return** plunging to **−6.0% or worse** (100.0).

### Gateway 11: Feed Message Congestion Tier

A four-tier ordinal severity rating ordered across **Calm**, **Busy**, **Congested**, and **Saturated**. It escalates to match the highest stress among three message-flow conditions: the **Inbound Quote Message Rate** reaching **25,000 msg/s or higher** (which immediately forces **Saturated**), **Order Round-Trip Gateway Latency** rising to **Nominal** (**Busy**), **Spike Warning** (**Congested**), or **Critical Latency** (**Saturated**), or the **Trading Session Schedule Phase** entering the **Closing Cross** (which also forces **Saturated**).

## 4. Layer 2: Intermediate Risk Synthesis & Desk Postures

At the second analytical layer, the desk combines the eleven primary gateways with foundational telemetry to establish nine operational regimes and composite exposure ratings.

### Regime 12: Market Access Permission Regime

A three-state categorical regime ordered across **Unrestricted Access**, **Restricted Access**, and **Blocked**. Maintaining **Unrestricted Access** requires that the **Gateway Throttle & Risk Alarm Tier** stays **Clear**, the **Flow Toxicity & Wash Trade Risk Index** remains strictly below **50.0**, and the **Correlation Breakdown & Alpha Decay Tier** stays **Stable**. Conversely, if the **Gateway Throttle & Risk Alarm Tier** rises to **Watch** or higher, or the **Flow Toxicity & Wash Trade Risk Index** reaches **50.0 or higher**, or the **Correlation Breakdown & Alpha Decay Tier** reaches **Stressed** or higher, market access is curtailed to **Restricted Access** (at intermediate stress around 50.0) or **Blocked** (as the worst input approaches 100.0).

### Regime 13: Execution Venue Routing Mode

A four-state categorical routing directive ordered across **Direct Market**, **Smart Router**, **Dark Only**, and **Suspended**. It is set by whichever is worse between the **Feed Message Congestion Tier** and the **Correlation Breakdown & Alpha Decay Tier**. When the more severe of the two sits at its first tier (**Calm** and **Stable**), routing uses **Direct Market**; at the second tier (**Busy** or **Stressed**), it shifts to **Smart Router**; when either reaches its third tier (**Congested** or **Breakdown**), routing restricts to **Dark Only**; and when either reaches its fourth tier (**Saturated** or **Margin Deficit**), routing is **Suspended**.

### Regime 14: Cross-Asset Liquidity Shock Multiplier

A continuous numerical metric bounded between **0.0 and 100.0** that measures contagious illiquidity across correlated instruments. It activates when four conditions hold simultaneously: **Infrastructure & Borrow Availability Health Mode** is not in **Critical Failure** (remaining **Nominal** at 100.0 inverted health or **Degraded** at 50.0 inverted health), **Composite Market Liquidity Stress** is **Elevated**, **Stressed**, or **Crisis**, **Sector Benchmark Correlation** has broken down strictly below **0.20**, and the **Overnight Opening Price Gap** is at **Moderate Gap** or **Extreme Gap**. The multiplier equals the lowest intensity across these four inputs.

### Regime 15: Gateway Rate-Limiting Severity Tier

A four-tier ordinal rating ordered across **Normal**, **Paced**, **Throttled**, and **Rate Limited**. It measures whether volatility-driven tick discrepancies require pre-emptive message pacing before hardware limits are breached. It escalates when the **Volatility & Tick Discrepancy Surge Factor** reaches **50.0 or higher**, provided at the same time that the **API Throttling Capacity Stage** has not yet hit **Red Rate Limit** (remaining at **Green**, **Yellow Burst**, or **Orange Throttled**, evaluated by its remaining headroom of 100.0 minus stage intensity) and the **Inbound Quote Message Rate** remains strictly below **25,000 msg/s** (90.0 inverted headroom). The tier is determined by the lowest intensity among those three conditions.

### Regime 16: News Sentiment Amplification Score

A continuous numerical score bounded between **0.0 and 100.0** that captures social-media and news shocks hitting an already dislocated market. It requires both the **Market Dislocation & Gamma Pressure Index** to sit at **50.0 or higher** and **News and Social Media Sentiment Momentum** to reach **2.5 sigma or higher**, taking the lower of the two intensities.

### Regime 17: Trading Desk Risk Execution Posture

A four-state categorical risk mandate ordered across **Aggressive**, **Neutral**, **Defensive**, and **Halted**. The desk shifts toward a more protective posture if any of four operational problems occur: the **Execution Latency & VWAP Quality Score** deteriorates below **50.0** (meaning its inverted stress is 50.0 or higher), **Master Emergency Kill Switch Readiness** is placed in **Risk Admin Standby** or **Auto Trigger Engaged**, **Sub-Penny Rule Minimum Price Variation Compliance** triggers a **Sub-Penny Warning** or **MPV Violation**, or the **API Throttling Capacity Stage** rises to **Yellow Burst**, **Orange Throttled**, or **Red Rate Limit**. The posture matches the single most severe stress among these four inputs.

### Regime 18: Liquidity Shock Vulnerability Tier

A five-tier ordinal vulnerability ranking ordered across **Resilient**, **Guarded**, **Vulnerable**, **Acute Stress**, and **Crisis**. It is governed by the worse of **Pre-Trade Order Validation Status** (**Suspicious** or **Rejected**) and **Composite Market Liquidity Stress** (**Calm** through **Crisis**), matching whichever of the two carries the higher risk intensity.

### Regime 19: Portfolio Drawdown Escalation Tier

A four-tier ordinal severity rating ordered across **Nominal**, **Elevated**, **High Loss**, and **Breach**. It escalates when any of three financial risk conditions worsen: the **Capital Drawdown & Depth Depletion Metric** rises to **50.0 or higher**, **Sector Benchmark Correlation** drops strictly below **0.20**, or the **Real-Time Market Volatility Index (VIX)** surges to **32.0 pts or higher**. The tier is set by whichever of these three conditions carries the highest risk intensity.

### Regime 20: Depth Depletion & Imbalance Pressure

A continuous numerical metric bounded between **0.0 and 100.0** that measures compound order-book exhaustion. It triggers only when four asymmetric stress conditions occur at the same time: the **Microstructure Imbalance Tier** is at **Moderate**, **Acute**, or **Extreme**, the **Correlation Breakdown & Alpha Decay Tier** is at **Breakdown** or **Margin Deficit**, **News and Social Media Sentiment Momentum** is at **2.5 sigma or higher**, and **Consolidated Book Depth** dries up strictly below **$50,000.0**. Its value is the lowest intensity across those four conditions.

## 5. Layer 3: Strategic Risk Gateways & Operational Controls

At the third analytical layer, the intermediate regimes are filtered through seven institutional governance controls.

### Control 21: Risk Firewall Gate Decision

A three-state categorical firewall verdict ordered across **Allow Flow**, **Throttle Flow**, and **Intercept Flow**. The firewall restricts or blocks order flow if any of three conditions occur: the **Market Access Permission Regime** moves to **Restricted Access** or **Blocked**, the **Gateway Rate-Limiting Severity Tier** rises to **Paced**, **Throttled**, or **Rate Limited**, or the **Market Dislocation & Gamma Pressure Index** reaches **50.0 or higher**. Taking the highest severity among the three, intermediate stress (around 50.0 to 66.67) places the firewall in **Throttle Flow**, while maximum stress (such as **Blocked**, **Rate Limited**, or a **100.0** dislocation index) forces **Intercept Flow**.

### Control 22: Master Kill Switch Readiness Tier

A four-tier ordinal readiness rating ordered across **Authorized**, **Standby**, **Armed**, and **Engaged**. It evaluates whether technical gateway alarms warrant arming the master kill switch while broader portfolio and liquidity conditions remain stable. Four conditions must hold simultaneously: the **Portfolio Drawdown Escalation Tier** remains contained at **Nominal** or **Elevated** (inverted stability score of 66.67 or higher), the **Liquidity Shock Vulnerability Tier** remains contained at **Resilient** or **Guarded** (inverted stability score of 75.0 or higher), the **Execution Latency & VWAP Quality Score** remains healthy at **50.0 or higher**, and the **Gateway Throttle & Risk Alarm Tier** escalates to **Throttle** or **Intercept** (intensity of 66.67 or 100.0). The readiness tier is governed by the lowest intensity across these four checks.

### Control 23: Strategy Operational State

A three-state categorical business continuity directive ordered across **Normal Operation**, **Reduce Exposure**, and **Emergency Shutdown**. It escalates based on whichever is more severe between **Depth Depletion & Imbalance Pressure** and the **Liquidity Shock Vulnerability Tier**. When **Depth Depletion & Imbalance Pressure** reaches **50.0 or higher** or the **Liquidity Shock Vulnerability Tier** reaches **Vulnerable**, the strategy moves to **Reduce Exposure**; when the **Liquidity Shock Vulnerability Tier** reaches **Acute Stress** or **Crisis** (or pressure reaches maximum intensity), the strategy enters **Emergency Shutdown**.

### Control 24: Systemic Sentiment Cascade Indicator

A continuous numerical indicator bounded between **0.0 and 100.0** that identifies self-reinforcing market cascades. It requires three conditions to hold at the same time: the **News Sentiment Amplification Score** is **50.0 or higher**, the **Capital Drawdown & Depth Depletion Metric** is **50.0 or higher**, and **Execution Venue Routing Mode** is restricted to **Dark Only** or **Suspended** (intensity 66.67 or 100.0). The indicator equals the lowest intensity among these three inputs.

### Control 25: Order Routing Compliance Verdict

A three-state categorical compliance verdict ordered across **Route Approved**, **Route Constrained**, and **Route Prohibited**. Order routing is restricted if any of three compliance triggers occur: the **Cross-Asset Liquidity Shock Multiplier** reaches **50.0 or higher**, **Pre-Trade Order Validation Status** flags flow as **Suspicious** or **Rejected**, or the **Gateway Throttle & Risk Alarm Tier** escalates to **Watch**, **Throttle**, or **Intercept**. Taking the worst of the three, moderate warnings move the verdict to **Route Constrained**, while severe breaches (such as **Rejected** validation or **Intercept** alarm tier) enforce **Route Prohibited**.

### Control 26: Position Deleveraging Threat Level

A five-tier ordinal threat ranking ordered across **Safe**, **Watch**, **Warning**, **Severe**, and **Critical**. It escalates when three active turbulence conditions converge simultaneously: **Trading Desk Risk Execution Posture** is **Defensive** or **Halted**, the **Microstructure Imbalance Tier** is **Moderate**, **Acute**, or **Extreme**, and the **Volatility & Tick Discrepancy Surge Factor** is **50.0 or higher**. The threat level is determined by the lowest intensity across those three active inputs.

### Control 27: Execution Feasibility Metric

A continuous numerical score bounded between **0.0 and 100.0** assessing whether venue liquidity can support active execution without adverse selection. A high feasibility score requires four healthy conditions to hold simultaneously: **Execution Venue Routing Mode** remains in **Direct Market** (100.0 inverted health) or **Smart Router** (66.67 inverted health), **Infrastructure & Borrow Availability Health Mode** stays **Nominal** (100.0 inverted health), the **Gateway Rate-Limiting Severity Tier** remains relaxed at **Normal** (100.0 inverted health) or **Paced** (66.67 inverted health), and the **Flow Toxicity & Wash Trade Risk Index** remains strictly below **50.0** (giving an inverted clean-flow score above 50.0). The metric is set by the lowest health score among these four requirements.

## 6. Layer 4: Executive Governance & Capacity Arbiters

At the fourth analytical layer, strategic risk controls converge into five executive arbiters that directly govern capital sizing and wind-down procedures.

### Arbiter 28: Portfolio Liquidation Policy Trigger

A three-state categorical policy trigger ordered across **No Action**, **Partial Deleverage**, and **Full Liquidation**. It escalates if any of three tail-risk conditions occur: the **Risk Firewall Gate Decision** moves to **Throttle Flow** or **Intercept Flow**, the **Systemic Sentiment Cascade Indicator** reaches **50.0 or higher**, or the **News Sentiment Amplification Score** reaches **50.0 or higher**. Taking the most severe of the three, intermediate stress (around 50.0) triggers **Partial Deleverage**, while maximum severity (100.0, such as **Intercept Flow**) triggers **Full Liquidation**.

### Arbiter 29: Block Execution Readiness Rank

A five-tier ordinal readiness rank ordered across **Unprepared** (0.0% capacity), **Low** (25.0% capacity), **Moderate** (50.0% capacity), **High** (75.0% capacity), and **Prime** (100.0% capacity). Achieving a high readiness rank requires four favorable conditions to hold at the same time: the **Position Deleveraging Threat Level** remains low at **Safe** (100.0 inverted safety) or **Watch** (75.0 inverted safety), the **Execution Feasibility Metric** is high (**75.0 or higher** for **Prime**), **Depth Depletion & Imbalance Pressure** remains low (strictly below **25.0**, giving an inverted calm score above 75.0 for **Prime**), and the **Risk Firewall Gate Decision** affirms **Allow Flow** (100.0 inverted openness). The rank is set by the lowest of these four readiness scores.

### Arbiter 30: Composite Block Trade Capacity Score

A continuous numerical score bounded between **0.0 and 100.0** representing instantaneous institutional block capacity. It requires four operational approvals at the same time: the **Order Routing Compliance Verdict** must be **Route Approved** (100.0 inverted approval), the **Execution Feasibility Metric** must be **50.0 or higher**, the **Strategy Operational State** must remain in **Normal Operation** (100.0 inverted health), and **Execution Venue Routing Mode** must remain in **Direct Market** (100.0 inverted health) or **Smart Router** (66.67 inverted health). The capacity score equals the lowest value among these four inputs.

### Arbiter 31: Algorithmic Governance Operating State

A three-state categorical operating state ordered across **Active Execution**, **Standby Pause**, and **Termination**. It escalates whenever either the **Strategy Operational State** moves to **Reduce Exposure** or **Emergency Shutdown**, or the **Risk Firewall Gate Decision** moves to **Throttle Flow** or **Intercept Flow**. Matching the more severe of the two, **Reduce Exposure** or **Throttle Flow** places governance into **Standby Pause**, while **Emergency Shutdown** or **Intercept Flow** places it into **Termination**.

### Arbiter 32: Inventory Unwind Urgency Level

A five-tier ordinal severity rating ordered across **Passive**, **Guarded**, **Elevated**, **Urgent**, and **Emergency**. It escalates when both the **Master Kill Switch Readiness Tier** is **Armed** or **Engaged** (intensity 66.67 or 100.0) and the **Trading Desk Risk Execution Posture** is **Defensive** or **Halted** (intensity 66.67 or 100.0), taking the lower intensity of the two.

## 7. Layer 5: Master Algorithmic Execution Directives

The final layer of the policy mandate establishes three definitive, legally binding execution directives for the trading desk.

| Directive | Protocol Type | Valid Operating Domain | Desk Decision Rule |
| --- | --- | --- | --- |
| **Directive 33: Block Trade Order Allocation** | Continuous Numerical (%) | 0.0% to 100.0% | Lower of Block Execution Readiness Rank capacity and Composite Block Trade Capacity Score |
| **Directive 34: Portfolio Liquidation Protocol** | Four-Tier Ordinal | No Liquidation, Soft Deleverage, Orderly Wind-Down, Emergency Flatten | Highest severity across Portfolio Liquidation Policy Trigger, Inventory Unwind Urgency Level, and Position Deleveraging Threat Level |
| **Directive 35: Master Algorithmic Operating Directive** | Three-State Categorical | Continue Trading, Suspend New Orders, Emergency Halt | Driven by Algorithmic Governance Operating State alongside Block Execution Readiness Rank and Composite Block Trade Capacity Score |

### Directive 33: Block Trade Order Allocation

* **Metric Nature & Bounds**: A continuous numerical percentage bounded between **0.0% and 100.0%**.
* **Desk Calculation**: Determined by comparing the percentage capacity of the **Block Execution Readiness Rank** (**Unprepared** = 0.0%, **Low** = 25.0%, **Moderate** = 50.0%, **High** = 75.0%, **Prime** = 100.0%) against the **Composite Block Trade Capacity Score** (**0.0% to 100.0%**), and taking whichever of the two numbers is **lower**.
* **Execution Constraint**: Both conditions must support execution simultaneously; if either **Block Execution Readiness Rank** is **Unprepared** (0.0%) or **Composite Block Trade Capacity Score** drops to **0.0%**, permissible block order sizing immediately drops to **0.0%**.

### Directive 34: Portfolio Liquidation Protocol

* **Metric Nature & Bounds**: A four-tier ordinal severity protocol ordered across **No Liquidation**, **Soft Deleverage**, **Orderly Wind-Down**, and **Emergency Flatten**.
* **Desk Calculation**: Determined by taking the **single highest risk intensity** across the **Portfolio Liquidation Policy Trigger**, the **Inventory Unwind Urgency Level**, and the **Position Deleveraging Threat Level**:
* **No Liquidation** (highest intensity strictly below **25.0**): Normal inventory balancing applies.
* **Soft Deleverage** (highest intensity from **25.0 to strictly below 50.0**): Aggressive liquidity taking is barred; inventory is reduced passively via resting midpoint orders.
* **Orderly Wind-Down** (highest intensity from **50.0 to strictly below 75.0**): Algorithms actively cross the spread on lit venues to reduce gross notional exposure by **50.0%** within **15 minutes**.
* **Emergency Flatten** (highest intensity of **75.0 or higher**): All quoting is terminated and execution algorithms immediately sweep all available lit and dark book depth to liquidate **100.0%** of open risk positions to cash.



### Directive 35: Master Algorithmic Operating Directive

* **Metric Nature & Bounds**: A three-state categorical governance command ordered across **Continue Trading**, **Suspend New Orders**, and **Emergency Halt**.
* **Desk Calculation**: Evaluates the **Algorithmic Governance Operating State** alongside the **Block Execution Readiness Rank** and **Composite Block Trade Capacity Score** (where loss of block readiness or capacity adds halt pressure equal to 100.0 minus their respective readiness scores):
* **Continue Trading** (overall halt intensity strictly below **35.0**): Authorizes full autonomous execution across all lit and dark venues when the **Algorithmic Governance Operating State** is in **Active Execution** and both block capacity arbiters confirm healthy readiness.
* **Suspend New Orders** (overall halt intensity from **35.0 to strictly below 65.0**): Enforced when the **Algorithmic Governance Operating State** enters **Standby Pause** or block capacity degrades moderately, preventing new position origination while permitting resting passive orders to be filled or canceled.
* **Emergency Halt** (overall halt intensity of **65.0 or higher**): Enforced immediately when the **Algorithmic Governance Operating State** reaches **Termination** or block execution capacity collapses. All active gateway sessions must cancel open resting orders instantly, reject inbound child order requests, and revoke exchange routing credentials.



## 8. Complete Decision Lineage & Supervisory Auditability

In strict compliance with SEC Rule 15c3-5 and MiFID II RTS 6, every automated directive is bidirectionally traceable across all five analytical layers back to its foundational surveillance indicators:

| Layer Level | Architecture Component | Node Count & Modalities |
| --- | --- | --- |
| **Layer 0** | 35 Primary Surveillance Indicators | 15 Numerical, 10 Ordinal, 10 Categorical |
| **Layer 1** | 11 Primary Risk Gateways | Gateways 1–11 (4 Numerical, 4 Ordinal, 3 Categorical) |
| **Layer 2** | 9 Intermediate Risk Regimes | Regimes 12–20 (3 Numerical, 3 Ordinal, 3 Categorical) |
| **Layer 3** | 7 Strategic Risk Controls | Controls 21–27 (2 Numerical, 2 Ordinal, 3 Categorical) |
| **Layer 4** | 5 Executive Capacity Arbiters | Arbiters 28–32 (1 Numerical, 2 Ordinal, 2 Categorical) |
| **Layer 5** | 3 Master Algorithmic Directives | Directives 33–35 (1 Numerical %, 1 Ordinal, 1 Categorical) |

1. **Audit Trace for Block Trade Order Allocation (Directive 33)**: Derived directly from **Block Execution Readiness Rank** (Arbiter 29) and **Composite Block Trade Capacity Score** (Arbiter 30), maintaining full causal lineage through 24 intermediate derived assessments and 33 primary telemetry inputs.
2. **Audit Trace for Portfolio Liquidation Protocol (Directive 34)**: Derived from **Portfolio Liquidation Policy Trigger** (Arbiter 28), **Inventory Unwind Urgency Level** (Arbiter 32), and **Position Deleveraging Threat Level** (Control 26), tracing exposure across 24 intermediate derived assessments and 32 primary telemetry inputs.
3. **Audit Trace for Master Algorithmic Operating Directive (Directive 35)**: Synthesizes **Algorithmic Governance Operating State** (Arbiter 31), **Block Execution Readiness Rank** (Arbiter 29), and **Composite Block Trade Capacity Score** (Arbiter 30) across 24 intermediate derived assessments and 33 foundational indicators.

## 9. Regulatory Compliance & Governance Attestation

1. **Formal Verification**: All domain bounds, ordinal tier progressions, threshold cutoffs, and simultaneous/escalation rules defined within this mandate have been formally verified as mathematically consistent, non-contradictory, and free from dead logic across all 70 nodes using Satisfiability Modulo Theories (SMT) theorem proving.
2. **Supervisory Change Control**: Any modification to variable bounds, threshold parameters, or risk escalation rules requires formal Risk Committee sign-off and automated regression verification prior to production deployment.
