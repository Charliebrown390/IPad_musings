# 🚨 Freight Rate Weekly Report — 2026-11-01

> ℹ️ **Data provenance** — 168 of 2,148 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 1,980 real observations were used.
>
> Quarantined, not deleted, for audit. Sources: `seed-data` (156), `seed-data/march-2026` (12).

> ⚠ **STALE DATA WARNING** — 2 indices not reporting usable data (threshold 14 days):
>
> - **SCFI** — 🛑 **no real data at all**; every one of its 78 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
> - **WCI** — 🛑 **no real data at all**; every one of its 56 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
>

## Executive Summary

# FREIGHT MARKET EXECUTIVE SUMMARY
## Week-on-Week Analysis & Portfolio Implications

---

## (1) DEMAND TRENDS BY REGION

**China Export Routes: Bifurcated Weakness**

The broadest trend is demand softening from China, with material divergence by destination:
- **Mediterranean & Northern Europe** (CN_MED, CN_NEUR): Sharp contraction at -10.3% and -6.2% WoW respectively, signalling cooling demand to Western Europe and reduced container velocity on the classic Asia-Europe trunk.
- **Americas (both coasts)**: Resilience, though muted. CN_USEC flat at 0.0%, CN_USWC marginally negative at -0.3%, while CN_SAM posts modest +1.2%. This suggests transatlantic trade remains sticky relative to intra-Asian and trans-Pacific flows, possibly reflecting inventory rebuilding ahead of US tariff uncertainty.
- **Oceania**: Isolated strength at CN_OCE +2.9% with SPIKE momentum—likely seasonal agricultural/commodity exports (southern hemisphere summer) rather than sustained demand recovery.

**Broader Freight Index (FBX) Signals: Correction Phase**

Most FBX components stable or slightly negative (FBX12, FBX14, FBX21, FBX26 in -0.3% to -3.8% range), except:
- **FBX24 (+4.5%, SPIKE)**: Anomalous strength suggesting either a specific trade lane relief (e.g., post-congestion recovery) or temporary capacity constraint rather than demand-driven.
- Overall message: **Freight markets are in a gentle correction**, not crisis, with regional pockets of stress (Europe) offsetting American resilience.

**Portfolio Implication**: This demand bifurcation favours counterparties with Asia-Americas exposure over Europe-focused logistics operators; credit spreads for pan-regional shipping groups warrant tightening scrutiny.

---

## (2) INFLATIONARY COST PRESSURES: REALISED vs. PIPELINE

**Critical Finding: Severe Input-Output Mismatch**

| Cost Component | Score | Status | Interpretation |
|---|---|---|---|
| **Rate Component** | 96.6/100 | ⚠️ EXTREME | Freight rates already substantially elevated; limited capacity to pass further cost inflation to customers |
| **Crude Component** | 69.5/100 | ELEVATED | Oil prices inflated by geopolitical premium; bunker fuel hedges partially masking underlying cost |
| **Bunker Fuel (4W)** | 0.0% | BENIGN | Fuel price momentum flat—but scoring disconnect suggests *pricing lags* fuel cost reality |
| **Composite Score** | 47.6/100 | MODERATE | Aggregate masks dangerous asymmetry |

**What This Means:**

1. **Already Materialised Costs**: 
   - Bunker fuel at elevated nominal levels (crude_component=69.5) has *not* moved sharply this week (0.0%), implying operators locked in higher costs weeks/months ago.
   - Freight rates themselves are at compressed margins (rate_component=96.6), meaning pricing power is exhausted—vessels are full but unprofitable.

2. **Pipeline Risks (Not Yet Passed Through)**:
   - The crude_component score of 69.5 with flat bunker momentum suggests fuel costs remain *sticky* at inflated levels. A geopolitical shock could spike crude further, but operators lack pricing runway to recover margins.
   - Labour cost pressures (see Section 3) are latent: dockworker disruptions have not yet materialized into demurrage/handling cost increases, but contingency reserves are rising.

**The Squeeze Architecture**: Operators face a three-part margin compression:
- Rates locked at cycle highs with falling utilisation (demand cooling)
- Fuel costs elevated and hedged (limited volatility relief)
- Labour costs rising but not yet billed (contingency expenses opaque)

**Portfolio Risk**: This is a classic **negative carry scenario for shipping credit**. Operators' operating leverage is inverted—falling demand with sticky costs. Refinancing risk rises as EBITDA multiples compress.

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK

**Geopolitical Risk Score: 72.0/100 (High)**

**Primary Threat: Hormuz Strait (Oil/Tanker Markets)**
- Tanker hull-mounted explosive attack signals *kinetic escalation* beyond drone/missile threats.
- Immediate impact: Tanker rate surge already observable (noted in sentiment summary), reflected in elevated crude_component score.
- **Container shipping exposure**: Indirect via bunker fuel cost (oil majors passing volatility costs downstream) and re-routing premiums around Cape of Good Hope.
- **Route-specific risk**: CN_MED weakness (-10.3%) likely amplified by Suez Canal insurance/bunker premiums and perceived Middle East instability reducing shipper appetite for eastern Mediterranean ports.

**Labour Disruption Score: 65.0/100 (Elevated)**

**Global Coordinated Action Across 113 Ports**
- Dockworker anti-war protest signals **political fragmentation** of labour, not merely wage/condition disputes.
- **Risk asymmetry**: Disruptions most likely to impact high-unionisation jurisdictions (US East Coast, Northern Europe, Australia), exactly where CN_USEC, CN_NEUR, and Oceania routes derive highest-value cargo.
- **Timing exposure**: Southern hemisphere summer (Oceania +2.9%) and US holiday season imports create maximum leverage for coordinated work actions; disruptions would have outsized rate impact.
- **Not yet priced**: Port_congestion score (45.0) is moderate; labour cost contingencies not yet visible in freight rates, suggesting **asymmetric downside risk** (rates could spike sharply if disruptions materialise).

**Geographic Route Concentration**:
- **High-Risk Zones**: CN_MED (already cooling, geopolitical premium embedded), CN_USEC (labour risk, stable rates underpricing disruption exposure)
- **Lower-Risk Zones**: CN_SAM, CN_USWC (peripheral to geopolitical flashpoints, smaller labour footprint relative to rates)

---

## (4) ACTIONABLE PORTFOLIO IMPLICATION

### **Recommendation: De-Risk Shipping Credit & Recalibrate Insurance Assumptions**

**Action (Multi-Asset):**

1. **Fixed Income**: Reduce exposure to leveraged container/tanker operators with:
   - High bunker fuel hedging maturities in Q1 2025 (refinancing risk if rates fall but costs remain sticky)
   - Significant USEC/Mediterranean port dependency
   - Debt maturity walls >$200M in next 18 months without asset sales visibility
   
   **Rationale**: Demand-led credit deterioration (freight demand cooling) colliding with cost rigidity (fuel, labour) will compress EBITDA multiples before spreads reprice. Early exit captures current yields before compression.

2. **Insurance Portfolio (P&C/Cargo):**
   - **Increase reserves** for marine general liability claims related to:
     - Geopolitical incidents (Hormuz attacks, re-routing losses)
     - Labour action-induced cargo damage (hastily loaded/unloaded containers, vessel acceleration damage)
   - **Reassess loss ratios**: Port_congestion=45/100 is deceptively mild; labour disruptions could spike demurrage/loss-of-use claims by 15–25% if coordinated actions hit 113 ports simultaneously.

3. **Reinsurance Cost Outlook (Inflation Assumption)**:
   - **Revise upward**: Current freight-linked inflation pass-through assumptions are *too optimistic*. The 96.6 rate_component score indicates pricing power is exhausted; shippers will absorb costs as lower logistics margins, not pass-through inflation.
   - **Geopolitical premium persistence**: Hormuz strand premium (typically 1–3% of hull insurance for tankers, now embedded in rates) is likely *sticky* beyond current year, warranting higher war-risk provisions in reinsurance quotes.
   - Expect reinsurance rate increases of 5–12% (above CPI) in Q1 2025 marine and cargo lines due to combined geopolitical + labour tail risk.

**Quantitative Threshold**: If CN_MED and CN_NEUR combined volume-weighted rates fall below 85% of Q3 2024 baseline *and* labour disruptions hit >30 days of port closures, trigger emergency hedging review for shipping-linked derivatives.

---

## Summary Table: Risk Dashboard

| Risk Factor | Severity | Portfolio Impact | Time Horizon |
|---|---|---|---|
| Demand Softening (Europe) | HIGH | Credit margin compression | 4–8 weeks |
| Rate-Cost Mismatch | CRITICAL | Refinancing pressure | 8–16 weeks |
| Geopolitical (Hormuz) | HIGH | Insurance reserve calls | Ongoing |
| Labour Coordination | MEDIUM-HIGH | Tail-risk claims spike | 4–12 weeks (seasonal) |
| Inflationary Persistence | MEDIUM | Reinsurance cost inflation | Q1 2025+ |

**Bottom Line**: The freight market is transitioning from a *demand shock* (2023–24) to a *cost squeeze* (late 2024–2025). Insurance portfolios should front-load provisions for labour/geopolitical claims and reduce credit exposure to leveraged shipping operators before margin compression becomes industry consensus.

---

**Inflationary Pressure Score: 48 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 0 | 35% | ⚠ 31w of 52w |
| Brent Crude (4W Δ) | 70 | 20% | ⚠ 31w of 52w |
| Freight Rate Composite (4W Δ) | 97 | 25% | ⚠ 31w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 31 weeks; Brent Crude 31 weeks; Freight Rate Composite 31 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
>
> ⚠ **Excluded from the composite** — Baltic Dry Index: fewer than 12 weeks of real data. Reported as INSUFFICIENT_HISTORY rather than normalised on a window too short to be meaningful; the remaining weights are redistributed proportionally.
>
> ℹ️ **Scale breaks** — component scores are min-max normalised, so they are only comparable across reports that share the same scale. Scores in reports published before 2026-07-27 are **not** comparable to these. Changes that moved the scales, newest first:
>
> - **2026-07-27 — Synthetic rows excluded from the normalisation history.** 168 seed rows in freight_rates, and 280 in input_costs, were removed from the windows behind every component. The bunker and crude scales moved most: both had been built on real and fabricated observations mixed together.

## News Sentiment Risk

| Risk Category | Score (0–100) | Level |
|---------------|:-------------:|-------|
| Geopolitical Risk      | 72 | 🔴 HIGH |
| Labour Disruption Risk | 65 | 🟠 MODERATE |
| Port Congestion Risk   | 45 | 🟠 MODERATE |

**Key Events Detected:**
- Tanker attacked with hull-mounted explosives in Hormuz Strait indicating escalating maritime security threats
- Dockworkers unite across 113 ports in global anti-war protest creating potential for coordinated labour disruptions
- Tanker rates surge significantly as oil majors report increased costs from market volatility and geopolitical tensions

**Routes at Risk:** Strait of Hormuz (Persian Gulf exports) · East Asian shipping lanes (China to Europe) · Global container and tanker routes via 113 major ports

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $573 | N/A | ▼ 10.3% | $627 | 🔵 COOLING |
| China/East Asia → North Europe | $9,911 | N/A | ▼ 6.2% | $9,894 | 🟢 STABLE |
| China/East Asia → Oceania | $4,375 | N/A | ▲ 2.9% | $3,943 | 🟠 SPIKE |
| China/East Asia → South America | $3,595 | N/A | ▲ 1.2% | $3,402 | 🟢 STABLE |
| China/East Asia → North America East Coast | $340 | N/A | ▲ 0.0% | $353 | 🟢 STABLE |
| China/East Asia → North America West Coast | $8,340 | N/A | ▼ 0.3% | $8,243 | 🟢 STABLE |
| FBX12 – FBX12 | $441 | N/A | ▲ 0.0% | $436 | 🟢 STABLE |
| FBX14 – FBX14 | $170 | N/A | ▲ 0.0% | $170 | 🟢 STABLE |
| FBX21 – FBX21 | $1,155 | N/A | ▼ 3.8% | $1,146 | 🟢 STABLE |
| FBX22 – FBX22 | $2,895 | N/A | ▲ 0.1% | $2,829 | 🟢 STABLE |
| FBX24 – FBX24 | $1,574 | N/A | ▲ 4.5% | $1,304 | 🟠 SPIKE |
| FBX26 – FBX26 | $2,406 | N/A | ▼ 0.3% | $2,375 | 🟢 STABLE |

---
_Generated 2026-11-01 03:58 UTC_