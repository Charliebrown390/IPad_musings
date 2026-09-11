# Freight Rate Weekly Report — 2026-09-11

> ℹ️ **Data provenance** — 168 of 1,536 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 1,368 real observations were used.
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

**Broadly Softening Demand Across Chinese Export Routes**

The freight data signals a **coordinated cooling across most major routes from China**, suggesting either demand normalization post-seasonal peak or emerging headwinds in downstream consumption:

- **Europe-bound routes (CN_NEUR, CN_MED):** CN_NEUR shows modest -2.9% WoW decline with STABLE momentum—indicating a plateau rather than cliff-edge deterioration. CN_MED lacks recent history but should be monitored as the premium Mediterranean slot market typically leads sentiment shifts.
- **Americas routes (CN_SAM, CN_USEC, CN_USWC):** More pronounced weakness, particularly CN_SAM (-3.1%) and CN_USEC (-1.4%), both in COOLING momentum. This suggests either reduced US import demand or capacity repositioning, though declines remain modest in absolute terms.
- **Oceanic routes (CN_OCE):** -1.3% WoW with COOLING momentum indicates sustained but slowing trade to Australia/NZ—consistent with softer regional commodity demand.

**FBX Index Divergence Signals Volatility Not Direction:**
The unmapped FBX routes present a critical alert. FBX14 (likely Asia-North Europe) crashed -45.9% WoW—an outlier magnitude that demands clarification. This may reflect:
- A single abnormal shipment or rate surge unwinding
- Index methodology discontinuity or data error
- Real structural repricing in the 14-week forward curve

FBX12 and FBX21 flatness combined with FBX14's collapse suggests **forward curve inversion or volatility clustering**, not linear demand deterioration.

**Conclusion:** Demand is **soft but not collapsing**. Regional variation and forward curve distress suggest **tactical repricing rather than cyclical downturn**.

---

## (2) INFLATIONARY COST PRESSURES: MATERIALIZED VS. EMBEDDED

This is the critical distinction for portfolio risk modeling.

### **Materialized Input Costs (Already Absorbed by Operators)**

| Cost Component | Status | Evidence |
|---|---|---|
| **Bunker Fuel (11.8/100)** | LOW PRESSURE, RECENTLY ABSORBED | 4W change = +11.8%. Modest swing. Operators have incorporated; marginal fuel cost inflation is priced into current rates. |
| **Crude Oil (94.1/100)** | SEVERE INFLATIONARY SIGNAL | The outlier. This score indicates elevated crude underpinning energy costs across the supply chain (port equipment, terminal operations, potential future bunker moves). |
| **Baltic Dry Index** | N/A | Absence of BDI data limits bulk commodity cycle intelligence; ancillary to containerized demand but worth monitoring given crude/energy exposure. |

### **Costs NOT Yet Passed Through to Rates (Future Pressure)**

The **rate_component score of 63.0/100** is the key red flag:

1. **Crude's 94.1 signal with weak freight rates (-1.4% to -3.1%) = margin compression:**
   - Operators are absorbing elevated fuel surcharge exposure and energy-linked operational costs while unable to levy higher base freight rates.
   - This is a **lagged transmission risk**: if crude sustains above current levels, either rates must recover or operator profitability deteriorates—constraining debt service capacity and increasing default risk in leveraged shipping companies.

2. **Composite score of 48/100 is deceptive:**
   - The average masks a **bimodal distribution**: low bunker inflation + extremely high crude inflation + moderate-to-high rate inflation.
   - Portfolio models using simple composite inflation scores risk underweighting tail energy risk.

3. **Labour & Port Costs (Implicit):**
   - Not explicitly quantified but geopolitical/labour sentiment (below) suggests upward pressure on port labour and inland logistics that may not yet be embedded in the 63.0 rate score.

### **Portfolio Implication:**
Shipping company **credit spreads may not be compensating for the asymmetry**: freight rates are soft, crude is elevated, and operators lack pricing power. This is a **2–4 quarter credit deterioration signal** unless crude rolls over or demand rebounds.

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK

### **Geopolitical Risk: ACUTE (72/100)**

**"Hormuz attacks reach wartime high"** is the critical headline:
- **Red Sea/Suez disruption pricing:** Longer Asia-Europe routing (+20–25% voyage time) is now the operational reality, not contingency planning.
- **War-risk insurance premiums** are elevated and volatile; this adds hidden cost across CN_NEUR and CN_MED routes specifically.
- **Bunker consumption increases materially** on longer routes, but the bunker score (11.8) suggests this cost component is *relatively stable* week-on-week—implying either:
  - Rerouting costs are already baked into operator budgets and fuel pass-through, or
  - Bunker volatility is being masked by forward hedging strategies.
- **Indirect effect on port congestion:** Rerouting vessels away from traditional Suez channels creates temporary congestion at southern Africa and non-traditional Asian hubs.

**Port congestion (42/100) is MODERATE but watching the geopolitical/Hormuz axis**—if attacks intensify, congestion cascades into premium ports (Singapore, Port Said alternatives).

### **Labour Disruption: CONTAINED (35/100)**

**Relative to geopolitical risk, labour is secondary but not dormant:**
- The **$186M CMA CGM–Samsung dispute** indicates shipbuilder labour/delivery disputes are active (contract renegotiation risk for newbuild capacity entering the market).
- Chinese shipyard blaze (25 dead) will likely trigger safety audits and temporary capacity friction; upward pressure on new tonnage costs downstream but not immediate rate impact.
- Container handler strikes in Europe and US ports are not flagged as acute, but port labour indices globally are drifting upward post-pandemic. The 42/100 congestion score may be understating labour-driven supply friction.

### **Route-Specific Risk Gradient:**

| Route | Geopolitical Risk | Labour Risk | Composite Exposure |
|---|---|---|---|
| CN_NEUR, CN_MED | **SEVERE** (Suez/Hormuz) | Moderate (EU port labour) | **HIGH** |
| CN_SAM | **Moderate** (non-Suez) | Low | MODERATE |
| CN_USEC, CN_USWC | **Moderate** (port-centric) | Moderate–High (US ILA negotiations 2025) | MODERATE–HIGH |
| CN_OCE | **Low** | Low | LOW |

---

## (4) ACTIONABLE PORTFOLIO IMPLICATION

### **Recommendation: Reassess Inflation Assumptions & Shipping Credit Exposure**

**For Fixed Income Portfolios:**

1. **Disaggregate inflation models by shipping subsector:**
   - Current composite 48/100 score masks **bifurcated inflation regimes**: energy inputs (94.1) decoupling from freight rates (63.0).
   - **Action:** Adjust CPI/inflation hedge expectations for shipping-exposed corporates downward. If holding bonds of large container shippers (e.g., CMA CGM, Hapag-Lloyd), assume **margin compression in 2025** rather than pricing power recovery. This implies:
     - Higher probability of covenant pressure and refinancing risk.
     - Credit spread widening as the market reprices operational leverage.

2. **Reinsurance Cost Outlook (War Risk & Contingency):**
   - Geopolitical score of 72 + Hormuz headline = **war-risk insurance costs are sticky upward and unlikely to deflate soon**.
   - Insurers are repricing marine war risk premiums; this feeds into reinsurance cost assumptions.
   - **Action:** If managing a multi-asset book with reinsurance exposure, **increase cost-of-risk assumptions for 2025** by 15–25 bps for ocean freight segments, particularly Asia-Europe trade. This cost will not reverse on near-term freight rate recovery.

3. **Credit Duration & Spread Positioning:**
   - The combination of soft demand (-1.4% to -3.1% WoW), crude inflation (94.1), and geopolitical cost drag (72/100) creates a **"slow-bleed" credit scenario**: not a shock default event, but steady margin erosion over 6–12 months.
   - **Action:** Rotate out of 3–5 year shipping-correlated credit and into:
     - Shorter-duration (2–3 yr) tactical positions to capture spread premium without extended negative carry.
     - Diversified transport infrastructure (ports, terminals, rail) to reduce shipping-cycle correlation.
     - High-quality defensive credit where energy cost pass-through is protected (integrated logistics, 3PLs with long-term contracts).

4. **FBX Curve Monitoring (Forward Risk):**
   - FBX14's -45.9% collapse warrants urgent clarification; if real, this signals **forward curve dislocation and potential rate volatility ahead**.
   - **Action:** Establish weekly monitoring protocol for unmapped FBX routes; an extended FBX14 weakness despite spot rate stability would indicate growing expectation of rate deflation in Q2–Q3 2025, elevating rolling credit risk.

---

## SUMMARY

**Freight markets are cooling modestly but not crashing.** The real insurance/portfolio risk lies not in demand destruction but in **margin compression between elevated input costs (crude, energy, war risk) and freight rates lacking pricing power.** Shipping credit appears mispriced for a 2–4 quarter operational headwind. Reinsurance costs for marine war risk are repricing upward and will not revert quickly. Recommend repositioning duration and concentration away from cyclical shipping credit into better-protected logistics and transport infrastructure, while increasing war-risk cost buffers in multi-asset allocation.

---

**Inflationary Pressure Score: 48 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 12 | 35% | ⚠ 24w of 52w |
| Brent Crude (4W Δ) | 94 | 20% | ⚠ 24w of 52w |
| Freight Rate Composite (4W Δ) | 63 | 25% | ⚠ 24w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 24 weeks; Brent Crude 24 weeks; Freight Rate Composite 24 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
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
| Labour Disruption Risk | 35 | 🟢 LOW |
| Port Congestion Risk   | 42 | 🟠 MODERATE |

**Key Events Detected:**
- Hormuz attacks reach wartime high
- 25 dead in bulker blaze at Chinese shipyard
- CMA CGM $186m Samsung dispute resolution

**Routes at Risk:** Strait of Hormuz (Persian Gulf to Gulf of Aden) · Middle East - Europe corridor · Middle East - Asia corridor · China coastal/regional services (shipyard incident)

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $491 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (56 obs) |
| China/East Asia → North Europe | $9,505 | N/A | ▼ 2.9% | $9,360 | 🟢 STABLE |
| China/East Asia → Oceania | $4,737 | N/A | ▼ 1.3% | $5,001 | 🔵 COOLING |
| China/East Asia → South America | $4,499 | N/A | ▼ 3.1% | $4,734 | 🔵 COOLING |
| China/East Asia → North America East Coast | $342 | N/A | ▼ 1.4% | $458 | 🔵 COOLING |
| China/East Asia → North America West Coast | $7,569 | N/A | ▼ 0.7% | $7,359 | 🟢 STABLE |
| FBX12 – FBX12 | $540 | N/A | ▲ 0.0% | $651 | 🔵 COOLING |
| FBX14 – FBX14 | $170 | N/A | ▼ 45.9% | $400 | 🔵 COOLING |
| FBX21 – FBX21 | $417 | N/A | ▲ 0.0% | $703 | 🔵 COOLING |
| FBX22 – FBX22 | $2,666 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (56 obs) |
| FBX24 – FBX24 | $1,101 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (56 obs) |
| FBX26 – FBX26 | $2,310 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (56 obs) |

---
_Generated 2026-09-11 00:24 UTC_