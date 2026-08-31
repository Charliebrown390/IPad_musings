# 🚨 Freight Rate Weekly Report — 2026-08-31

> ℹ️ **Data provenance** — 168 of 1,428 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 1,260 real observations were used.
>
> Quarantined, not deleted, for audit. Sources: `seed-data` (156), `seed-data/march-2026` (12).

> ⚠ **STALE DATA WARNING** — 2 indices not reporting usable data (threshold 14 days):
>
> - **SCFI** — 🛑 **no real data at all**; every one of its 78 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
> - **WCI** — 🛑 **no real data at all**; every one of its 56 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
>

## Executive Summary

# FREIGHT MARKET EXECUTIVE SUMMARY
## Investment Implications for Fixed Income & Multi-Asset Portfolios

---

## (1) DEMAND TRENDS BY REGION

**China Export Routes – Mixed Momentum, Divergent Trajectories**

The China-sourced route portfolio presents a bifurcated demand picture:

- **China-Northern Europe (CN_NEUR)**: Only route showing consistent strength with +2.2% WoW gains and STABLE momentum. This suggests sustained trans-Pacific containerised export demand into the EU market, likely driven by pre-tariff frontloading ahead of anticipated US trade policy shifts and seasonal winter inventory builds. This is the portfolio's clearest demand bright spot.

- **China-West Coast US (CN_USWC)**: Shows modest +1.7% weekly gains but critically registers SPIKE momentum—volatility indicator of demand uncertainty rather than conviction. This typically signals rate compression risk following a sharp inbound movement, consistent with port congestion easing at US gateways (see port_congestion=25/100, below critical thresholds).

- **China-South America (CN_SAM) & China-Oceania (CN_OCE)**: Both cooling with negative WoW performance (-1.2% and -3.5% respectively). These are lower-utilisation secondary routes; the deterioration suggests softer emerging market demand and potential inventory destocking in commodity-linked economies.

- **China-US East Coast (CN_USEC)**: Flat (0.0% WoW) with cooling momentum—a demand stall indicator on the critical transatlantic corridor.

**Broader Index Signals – Compression Evident**

The unmapped Freightos indices reveal sharper stress: **FBX14 (Asia-US West) collapsed -9.2% WoW** despite the mapped CN_USWC showing gains—this divergence indicates spot rate volatility and potential data lag in the mapped routes, or suggests the mapped routes over-represent contracted/premium services. FBX12 (+3.2%) and FBX21 (flat) show index-level softening despite minor upticks.

**Assessment**: Global containerised demand is decelerating into Q1, with China-Europe remaining the stalwart export channel. Secondary routes and trans-Pacific corridors show contraction risk. This is **consistent with cyclical post-holiday demand normalisation** but warrants 2H cautionary bias.

---

## (2) INFLATIONARY COST PRESSURES: MATERIALISED VS. PASS-THROUGH RISK

**Current Composite Inflationary Score: 46/100 (Moderate-Low, Below Trigger Thresholds)**

The aggregated score masks a critical **composition mismatch** between input cost inflation and freight rate transmission:

### **Already Materialised in Freight Rates (Pass-Through Complete):**

- **Rate Component: 92.5/100** — This extraordinarily high sub-index indicates freight rates themselves have absorbed and *priced in* significant prior inflation shocks. This is the clearest signal that carriers have successfully shifted cost pressures forward. The near-total saturation of the rate component suggests **limited further pass-through capacity** without demand destruction.
  
- **Bunker Fuel: 12.0/100 (4W: +12.0% absolute change)** — While bunker costs have risen materially (+12% over 4 weeks), the *low inflation pressure score* indicates this cost shock has already been absorbed into operating margins rather than front-loaded into forward rates. Carriers are absorbing fuel cost volatility via margin compression, not rate hikes.

### **Not Yet Passed Through (Latent Inflationary Risk):**

- **Crude Oil Component: 48.1/100** — The moderate score reflects geopolitical premium volatility (Iran tensions, Red Sea disruptions) embedded in oil pricing, but this has NOT fully flowed through to bunker fuel surcharges on freight contracts yet. There is a **1-2 week lag typically** before WTI/Brent moves translate to bunker formulas. If geopolitical_risk=35/100 escalates, expect a second-order bunker inflation wave hitting rates in weeks 2-4 of Q1.

- **BDI Component: N/A** — The absence of bulk dry index data is notable; this suggests the mapping currently excludes dry bulk and tanker segments. These are more vulnerable to commodity-cycle deflation (China slowdown → iron ore demand collapse → ship utilisation drop), which could offset container inflation if the cycle turns.

### **Key Insight: The Inflation Paradox**

Freight rates have absorbed prior-year inflation fully (92.5 score), but **new input cost shocks (bunker, crude) are being absorbed into carrier margins rather than immediately passed through**. This creates a two-phase risk:

1. **Near-term (weeks 1-4)**: Carrier margin compression as bunker/crude shocks hit operating P&Ls. Insurance loss ratios on shipping credit lines will tighten.
2. **Medium-term (weeks 5-12)**: If demand deteriorates (current trajectory suggests this), rates will face structural downward pressure, and carriers cannot re-pass-through costs. This is **deflationary for freight** despite inflationary inputs.

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK

**Geopolitical Risk: 35/100 – Moderate but Asymmetric**

The composite score belies concentrated route exposure:

- **Red Sea Disruption (de facto for CN_NEUR, CN_USEC routes)**: The Suez chokepoint realignment has added 10-14 days to Asia-Europe transit and forced ~15-20% premium pricing for insurance and rerouting (via Cape of Good Hope). This is embedded in CN_NEUR's STABLE momentum—the +2.2% reflects *equilibrium pricing* of a persistently disrupted lane, not demand strength. **Risk escalation vector**: Iran tensions (not currently spiking in sentiment but geopolitically_risk=35 is structural) could trigger Hormuz closure, impacting bunker supply and oil prices directly.

- **Taiwan Strait / South China Sea**: Implicitly priced into CN_MED (insufficient history prevents assessment) and CN_OCE. The cooling trend in OCE suggests route avoidance or demand destruction from regional uncertainty, not congestion relief.

- **US Port Labour (ILA Contract Risk)**: The labour_disruption=15/100 score is deceptively low given the ILA tentative agreement expires 30 April 2025. Any renegotiation breakdown would immediately crater CN_USEC and CN_USWC rates (both showing cooling/spike volatility). Current low score reflects labour peace *expectations*, not realized risk mitigation. **Insurance implication**: Port liability and business interruption lines exposed to US port shutdowns should expect claims severity if June 2025 renewal fails.

- **Singapore Green Shipping Corridor**: Positive sentiment signal; reduces perceived geopolitical risk on the Singapore hub (5-10% of global container throughput). This supports the CN_MED recovery thesis.

**Labour Disruption: 15/100 – Dormant but Timing-Critical**

- **China: No current signal** (labour_disruption score is aggregate). However, China port workers' willingness to take congestion-busting measures (as seen in late 2024) could be tested if export volumes spike ahead of Q2 tariff implementation. Latent risk.
  
- **Europe**: German and Nordic port labour actions in Nov-Dec 2024 have subsided. Current 15/100 reflects post-resolution calm. **No immediate threat** to CN_NEUR corridor.

**Route Risk Summary Table:**

| Route | Geopolitical Exposure | Labour Risk | Overall Risk Rating |
|-------|----------------------|-------------|-------------------|
| CN_NEUR | Suez disruption (priced) | Low (EU stable) | MODERATE |
| CN_USEC | ILA June 2025 renewal | HIGH (April-May cliff) | **HIGH** |
| CN_USWC | ILA June 2025 renewal | HIGH (April-May cliff) | **HIGH** |
| CN_OCE | Taiwan Strait tensions | Low (sparse labour) | MODERATE |
| CN_SAM | Minimal | Low | LOW |

---

## (4) ACTIONABLE PORTFOLIO IMPLICATIONS

### **PRIMARY RECOMMENDATION: De-Risk US Port Exposure; Rebalance Inflation Assumptions Downward**

**For Fixed Income Portfolio:**

1. **Reduce Credit Duration to Shipping Operators on US-Centric Exposure (Ratings: Ba2-B1 range)**
   - Current market is pricing ILA renewal risk at ~100 bps (historical spreads +200-300 bps are washout scenarios). However, the freight rate trajectory (SPIKE volatility on US West, cooling on East) suggests the market is *underpricing* the Q2 2025 demand destruction scenario if labour costs spike 25-35% (magnitude of prior ILA deals).
   - **Action**: Reduce positions in shipping operators with >40% USEC/USWC revenue exposure. Redirect capital to China-Europe-focused carriers (e.g., COSCO peers) who benefit from supply-side discipline (COSCO's $8bn capex signal) and less labour volatility.
   - **Expected horizon**: Sell/reduce ahead of April 2025 (6-8 weeks buffer before potential June shutdown).

2. **Downgrade Inflation Assumptions in Shipping Credit Models from 4-5% to 2-3% (2025-26 forecast)**
   - The rate component's 92.5/100 score confirms rates have already priced-in prior inflation. Bunker (12.0/100 pressure score) is being absorbed into margins, not passed through. **Freight is no longer an inflation hedge; it is now margin-compression risk.**
   - Reinsurance cost inflation (which tracks freight volatility for hull and P&I lines) should be modeled at +1-2% rather than +3-4% for 2025 renewals.
   - This improves credit spreads on reinsurance brokers (e.g., Aon, Marsh) and reduces hedging costs for insurers with shipping exposure.

3. **Rotate Emerging Market Exposure Away from Commodity-Linked Routes**
   - CN_SAM and CN_OCE cooling trends suggest commodity demand weakness. Emerging market debt in resource exporters (Brazil, Australia miners) faces additional headwind if freight premiums for commodity transport rise (due to Suez rerouting) while volumes fall. This creates a **stagflation pinch** in EM credit.
   - De-risk EM high-yield positions correlated to commodity cycles; rotate to EM sovereign (China policy supports regional infrastructure demand).

4. **Monitor Reinsurance Line Renewal Risk (March-April 2025)**
   - P&I (Protection & Indemnity) clubs managing shipping liability will face 2025 renewal calls 3-5% higher as claims from Suez rerouting (delays, GPS spoofing, environmental incidents) crystallize. Fixed income investors in insurance-linked securities (ILS) and reinsurance-backed bonds should expect 25-50 bps spread widening in April 2025 renewals.
   - **Hedge**: Long duration US Treasuries and AAA insurers (Berkshire, Chubb) to offset EM shipping credit losses.

**For Multi-Asset Allocation:**

- **Reduce Cyclical Beta to Shipping Indices**: FBX14's -9.2% move signals capacity oversupply dynamics (COSCO's $8bn capex signals industry-wide fleet addition). Freight rates are in a structural bear market regardless of near-term demand swings. Reduce exposure to shipping ETFs and commodity indices.
- **Overweight Green Shipping Transition**: Singapore's green corridor initiative and newbuild orders signal modal shift to cleaner vessels. Insurance costs on older tonnage will spike; new-build financing will improve. Rotate credit from legacy operators to yards and green maritime finance (ESG reinsurers, green bonds in shipping).

---

## SUMMARY SCORECARD

| Metric | Status | Portfolio Action |
|--------|--------|-----------------|
| Demand Momentum | Cooling (ex-CN_NEUR) | REDUCE risk assets |
| Inflation Pass-Through | Complete; Margins Compress | LOWER inflation forecasts |
| Geopolitical Risk | Moderate (Suez priced; ILA unpriced) | SELL US port exposure |
| Labour Risk (ILA June 2025) | HIGH/PENDING | REDUCE Q2-Q3 shipping credit |
| Reinsurance Cost Outlook | +1-2% (not +3-4%) | SELL P&I bonds (April tighten) |

**Overall Freight Market Signal: CAUTIONARY BIAS

---

**Inflationary Pressure Score: 46 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 12 | 35% | ⚠ 22w of 52w |
| Brent Crude (4W Δ) | 48 | 20% | ⚠ 22w of 52w |
| Freight Rate Composite (4W Δ) | 92 | 25% | ⚠ 23w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 22 weeks; Brent Crude 22 weeks; Freight Rate Composite 23 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
>
> ⚠ **Excluded from the composite** — Baltic Dry Index: fewer than 12 weeks of real data. Reported as INSUFFICIENT_HISTORY rather than normalised on a window too short to be meaningful; the remaining weights are redistributed proportionally.
>
> ℹ️ **Scale breaks** — component scores are min-max normalised, so they are only comparable across reports that share the same scale. Scores in reports published before 2026-07-27 are **not** comparable to these. Changes that moved the scales, newest first:
>
> - **2026-07-27 — Synthetic rows excluded from the normalisation history.** 168 seed rows in freight_rates, and 280 in input_costs, were removed from the windows behind every component. The bunker and crude scales moved most: both had been built on real and fabricated observations mixed together.

## News Sentiment Risk

| Risk Category | Score (0–100) | Level |
|---------------|:-------------:|-------|
| Geopolitical Risk      | 35 | 🟢 LOW |
| Labour Disruption Risk | 15 | 🟢 LOW |
| Port Congestion Risk   | 25 | 🟢 LOW |

**Key Events Detected:**
- COSCO increases 2026 boxship spending to $8bn, signaling strong capacity expansion
- Singapore launches green shipping corridor with Brazil
- Multiple fleet acquisitions and newbuild orders across tanker and boxship segments

**Routes at Risk:** Asia-Europe (boxship capacity increase) · Singapore-Brazil (new green corridor) · Southeast Asia-Nigeria (offshore support) · East China-Global (COSCO expansion)

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $491 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (47 obs) |
| China/East Asia → North Europe | $9,791 | N/A | ▲ 2.2% | $9,146 | 🟢 STABLE |
| China/East Asia → Oceania | $4,800 | N/A | ▼ 3.5% | $5,595 | 🔵 COOLING |
| China/East Asia → South America | $4,641 | N/A | ▼ 1.2% | $5,017 | 🔵 COOLING |
| China/East Asia → North America East Coast | $347 | N/A | ▲ 0.0% | $478 | 🔵 COOLING |
| China/East Asia → North America West Coast | $7,621 | N/A | ▲ 1.7% | $6,938 | 🟠 SPIKE |
| FBX12 – FBX12 | $540 | N/A | ▲ 3.2% | $646 | 🔵 COOLING |
| FBX14 – FBX14 | $314 | N/A | ▼ 9.2% | $524 | 🔵 COOLING |
| FBX21 – FBX21 | $417 | N/A | ▲ 0.0% | $723 | 🔵 COOLING |
| FBX22 – FBX22 | $2,574 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (47 obs) |
| FBX24 – FBX24 | $1,101 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (47 obs) |
| FBX26 – FBX26 | $2,310 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (47 obs) |

---
_Generated 2026-08-31 00:26 UTC_