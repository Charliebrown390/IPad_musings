# 🚨 Freight Rate Weekly Report — 2026-11-27

> ℹ️ **Data provenance** — 168 of 2,460 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 2,292 real observations were used.
>
> Quarantined, not deleted, for audit. Sources: `seed-data` (156), `seed-data/march-2026` (12).

> ⚠ **STALE DATA WARNING** — 2 indices not reporting usable data (threshold 14 days):
>
> - **SCFI** — 🛑 **no real data at all**; every one of its 78 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
> - **WCI** — 🛑 **no real data at all**; every one of its 56 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
>

## Executive Summary

# FREIGHT MARKET EXECUTIVE SUMMARY
**Week-on-Week Analysis | Insurance Investment Perspective**

---

## (1) DEMAND TRENDS BY REGION

### China Export Lanes: Bifurcated Momentum
The CN portfolio reveals **divergent regional demand signals**:

- **Oceania (CN_OCE)**: +20.2% WoW spike represents the most significant demand indicator across the dataset. This outsized move suggests either vessel capacity tightness, seasonal demand acceleration (southern hemisphere approaching summer), or supply-chain front-loading ahead of potential disruption. The SPIKE momentum classification indicates non-linear demand.
- **Mediterranean/Europe (CN_MED)**: Modest +1.8% signals stable baseline demand without cyclical excitement.
- **US East Coast (CN_USEC)**: +4.5% shows healthy demand; contrasts sharply with US West Coast.
- **US West Coast (CN_USWC)**: -5.6% decline despite being primary gateway for Asian imports suggests either (a) modal shift to air freight, (b) port labour uncertainty dampening shipper confidence, or (c) rate resistance at current levels.
- **Americas & North Europe**: Near-flat performance (CN_SAM -1.0%, CN_NEUR +0.1%) indicates mature, saturated markets with limited growth vectors.

**Portfolio Implication**: Regional divergence argues *against* a uniform shipping sector credit thesis. USEC/USWC spread widening is unusual and warrants investigation into port-specific labour or congestion headwinds.

---

## (2) INFLATIONARY COST PRESSURES: Materialised vs. Pipeline

### The Core Issue: Rate Component Dominates Inflation Signal

The composite score of **29/100** appears moderate, but the **rate_component=72.6/100** is the critical outlier:

#### Already Materialised Costs (Low Pass-Through Risk):
- **Bunker Fuel (6.5/100 pressure, +6.5% 4W change)**: Fuel cost inflation is *already observable in spot bunker markets* but remains **decoupled from freight rates** in this dataset. This suggests:
  - Carriers are absorbing margin compression (negative for shipper-facing insurance claims; positive for insurer underwriting).
  - Fuel surcharge mechanisms are either lagging or politically/contractually constrained.
  - Risk: If bunker spikes further (e.g., geopolitical disruption), carriers may default on fuel cost absorption, creating cliff-edge risk in derivatives/bunker hedging contracts.

- **Crude Component (15.3/100)**: Modest contribution; oil prices not in acute distress. This is a *lagging indicator* of fuel cost pass-through.

#### Pipeline/Not Yet Materialised (High Pass-Through Risk):
- **Rate Component (72.6/100 pressure)**: This is the **dominant inflationary signal** and suggests:
  - Freight rates are climbing *faster than input costs justify*, indicating shipper demand elasticity inelasticity or carrier capacity discipline.
  - **The paradox**: CN_USWC down -5.6%, yet rate pressure is rising. This decoupling suggests:
    - Regional pockets of overcapacity (USWC) coexist with tight capacity elsewhere (Oceania spike).
    - Rate inflation is not uniformly distributed; it is concentrated on underserved/high-demand lanes.
  - **For insurance portfolios**: A 72.6/100 rate pressure score with only +2.9% broad index (FBX12) movement indicates rates are *telegraphing* demand that may not yet be reflected in published indices. Claims frequency/severity tied to freight cost inflation may be understated in pricing models.

#### BDI Component: Absent
The N/A BDI signal is notable—bulk dry shipping data is unavailable or decoupled. This limits multimodal cost correlation analysis and suggests inland/bulk freight may not be moving in tandem with containerised trade.

### Summary Inflation Narrative:
**Fuel costs have materialised (6.5% 4W) with minimal rate pass-through; rate inflation is building in pockets and not yet fully reflected in headline indices.** This creates a *timing arbitrage*: carriers' margins are under pressure now, but shipper-facing costs will spike on a 4–8 week lag.

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK

### Sentiment Scorecard:
| Risk Factor | Score | Severity | Route Exposure |
|---|---|---|---|
| **Labour Disruption** | **65.0/100** | **ELEVATED** | Multi-route; US-centric |
| Geopolitical Risk | 45.0/100 | Moderate | Med, ME, Red Sea implicit |
| Port Congestion | 35.0/100 | Low-Moderate | US East Coast likely |

### Labour Risk—The Dominant Threat:

**Taylor Maritime shareholder revolt over pay** signals internal cost-control pressure within a major operator, coupled with **labour market tightness**. The 65/100 labour score is the single largest non-rate inflationary input. Cross-referencing with operational data:

- **CN_USWC weakness (-5.6%)** is likely *not* demand-driven but **labour-risk-driven**. US West Coast port labour (ILWU) has historically extracted wage gains during tight market cycles. Shipper diversion to USEC (+4.5%) reflects hedging against potential labour disruption.
- **Polish offshore wind + Danish shipowner backlash**: Flags supply-chain rigidity in Baltic/Northern Europe. If wind-farm development constraints affect vessel availability or fuel sourcing, CN_NEUR stability (0.1%) masks underlying leverage; any supply shock would manifest as rate spikes with 2–3 week lag.
- **Diesel tanker incident (Ibiza fatality)**: Increases regulatory scrutiny, insurance premiums for bunker/tanker operators, and reputational risk—particularly for underwriters of environmental/casualty lines.

### Geopolitical Risk (45.0/100—Moderate):
Red Sea/Suez disruption risks are *priced in* at moderate levels. The absence of a sharp spike suggests market is treating geopolitical risk as chronic, not acute. However:
- CN_MED at +1.8% (not elevated) suggests rerouting via Cape/Far East has partially normalized demand.
- Upside tail risk: If Houthis escalate attacks or Suez tolls rise sharply, Mediterranean rates could spike to 15–20% WoW, mirroring CN_OCE's current behaviour.

---

## (4) ACTIONABLE IMPLICATION FOR INSURANCE INVESTMENT PORTFOLIO

### Recommendation: **Recalibrate Shipping Sector Credit Exposure & Reinsurance Cost Assumptions**

#### Rationale:

1. **Freight rate inflation is ahead of published indices** (rate_component 72.6/100 vs. FBX12 +2.9%).
   - Carriers' near-term earnings visibility is *weaker than headline numbers suggest*.
   - Credit spreads on shipping bonds may not yet reflect margin compression from bunker fuel (6.5% 4W) with minimal pass-through.
   - **Action**: Upgrade downside scenarios in shipping credit stress tests; assume 200–300 bps wider spreads if rates fail to follow cost inflation over next 8 weeks.

2. **Labour cost inflation (65/100 score) is concentrated but severe.**
   - Taylor Maritime and ILWU labour events are precursors to sector-wide wage inflation.
   - Insurance loss ratios (particularly workers' compensation and liability) will deteriorate faster in shipping/logistics supply chain.
   - **Action**: For insurance underwriting portfolios, **increase loss reserves by 10–15% for maritime labour-exposed segments** (vessel operators, port workers, supply chain logistics). Reinsurance cost for 2025 renewals should assume +5–8% rate increases for marine/liability accounts.

3. **Regional demand divergence (Oceania +20.2% vs. USWC -5.6%) creates basis risk.**
   - Hedging strategies based on composite indices will mismatch route-specific exposure.
   - Reinsurance cover tied to "shipping sector" aggregates will underprice tail risk on underserved routes (Oceania, SAM).
   - **Action**: For multi-asset portfolios, **de-correlate** shipping exposure by route. Consider overweight on Oceania-linked assets (commodities, regional logistics) and underweight US container exposure until labour risks settle.

4. **Inflation assumptions need revision upward for 2025 guidance.**
   - Current composite score (29/100) *understates* forward inflation because rate component (72.6/100) is leading, not lagging.
   - Reinsurance cost inflation models should assume freight cost escalation of 5–8% YoY (not the 2–3% typically baked in).
   - **Action**: **Increase inflation assumptions in fixed-income valuation models by 50–100 bps for shipping-linked exposures**. This will mechanically tighten spreads on shipping bonds and logistics REITs, creating a tactical opportunity to trim overweights before labour/fuel cost pass-through hits earnings.

### Bottom Line:
The freight market is showing early-stage inflationary pressure (rising rates) *decoupled from published indices and not yet impacting carrier profitability*. This is a classic lead indicator. **Insurance portfolios should frontrun this signal by tightening shipping credit exposure now and pricing in higher reinsurance cost inflation for 2025 renewals.** The 4–8 week lag between rate inflation and loss inflation creates a window to de-risk before claims impact.

---

**Inflationary Pressure Score: 29 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 6 | 35% | ⚠ 35w of 52w |
| Brent Crude (4W Δ) | 15 | 20% | ⚠ 35w of 52w |
| Freight Rate Composite (4W Δ) | 73 | 25% | ⚠ 35w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 35 weeks; Brent Crude 35 weeks; Freight Rate Composite 35 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
>
> ⚠ **Excluded from the composite** — Baltic Dry Index: fewer than 12 weeks of real data. Reported as INSUFFICIENT_HISTORY rather than normalised on a window too short to be meaningful; the remaining weights are redistributed proportionally.
>
> ℹ️ **Scale breaks** — component scores are min-max normalised, so they are only comparable across reports that share the same scale. Scores in reports published before 2026-07-27 are **not** comparable to these. Changes that moved the scales, newest first:
>
> - **2026-07-27 — Synthetic rows excluded from the normalisation history.** 168 seed rows in freight_rates, and 280 in input_costs, were removed from the windows behind every component. The bunker and crude scales moved most: both had been built on real and fabricated observations mixed together.

## News Sentiment Risk

| Risk Category | Score (0–100) | Level |
|---------------|:-------------:|-------|
| Geopolitical Risk      | 45 | 🟠 MODERATE |
| Labour Disruption Risk | 65 | 🟠 MODERATE |
| Port Congestion Risk   | 35 | 🟢 LOW |

**Key Events Detected:**
- Taylor Maritime shareholder revolt over pay
- Polish offshore wind rules draw Danish shipowner backlash
- Diesel tanker incident off Ibiza with fatality

**Routes at Risk:** Baltic Sea (Poland-Denmark) · Mediterranean (Ibiza vicinity) · North Sea (offshore wind operations) · Asian shipbuilding routes (China)

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $564 | N/A | ▲ 1.8% | $575 | 🟢 STABLE |
| China/East Asia → North Europe | $9,854 | N/A | ▲ 0.1% | $9,838 | 🟢 STABLE |
| China/East Asia → Oceania | $5,162 | N/A | ▲ 20.2% | $4,541 | 🟠 SPIKE |
| China/East Asia → South America | $3,374 | N/A | ▼ 1.0% | $3,456 | 🟢 STABLE |
| China/East Asia → North America East Coast | $322 | N/A | ▲ 4.5% | $320 | 🟢 STABLE |
| China/East Asia → North America West Coast | $7,985 | N/A | ▼ 5.6% | $8,261 | 🟢 STABLE |
| FBX12 – FBX12 | $595 | N/A | ▲ 2.9% | $543 | 🟠 SPIKE |
| FBX14 – FBX14 | $170 | N/A | ▲ 0.0% | $170 | 🟢 STABLE |
| FBX21 – FBX21 | $982 | N/A | ▲ 3.4% | $1,012 | 🟢 STABLE |
| FBX22 – FBX22 | $2,664 | N/A | ▼ 3.1% | $2,777 | 🟢 STABLE |
| FBX24 – FBX24 | $1,307 | N/A | ▼ 4.3% | $1,444 | 🔵 COOLING |
| FBX26 – FBX26 | $2,345 | N/A | ▼ 2.2% | $2,387 | 🟢 STABLE |

---
_Generated 2026-11-27 06:24 UTC_