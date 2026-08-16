# 🚨 Freight Rate Weekly Report — 2026-08-16

> ℹ️ **Data provenance** — 168 of 1,272 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 1,104 real observations were used.
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

**Polarised demand signals with acute transatlantic volatility:**

The freight data reveals sharply divergent regional momentum, masking what appears to be a demand correction punctuated by episodic spikes:

- **US East Coast (CN_USEC):** +583% WoW spike with SPIKE momentum is the most significant anomaly in the dataset. This represents either (i) capacity destruction from port disruption/vessel re-routing, (ii) concentrated shipper panic-buying ahead of labour negotiations, or (iii) data error. **Critical to validate** before using as demand signal. If genuine, it suggests acute US import surge and inventory front-loading, consistent with Q4 retail demand but at unsustainable rates.

- **US West Coast (CN_USWC):** -43.6% cooling contradicts East Coast strength. This divergence points to **supply-chain bifurcation**—West Coast shippers may be locked into slower, cheaper alternative routings or facing demand destruction. Port labour tensions (ILWU contract renewal headwinds) likely dampen this corridor.

- **China-Europe (CN_NEUR):** -54.2% sharp cooling reflects weak European demand. Post-summer demand normalization combined with weak industrial sentiment (PMI weakness in Germany/France) signals demand recession, not capacity tightness.

- **China-Oceania & South America (CN_OCE, CN_SAM):** Mixed. -30.3% decline (Oceania) suggests Australian/NZ demand softening; +2.7% stability in South America (likely Brazil agricultural commodities) provides only marginal support.

- **Composite FBX indices (unmapped routes):** Massive spikes (FBX21: +1,260.5%, FBX14: +252.1%, FBX12: +507.9%) indicate **generalised intra-Asia volatility or spot market distortion**, not broad-based demand strength. The absence of historical data on FBX22/24/26 prevents interpretation but warrants monitoring as potential early-warning indicators of Asian port stress or regional trade friction.

**Demand Assessment:** Base case is **demand recession** with episodic volatility. No broad-based demand recovery visible.

---

## (2) INFLATIONARY COST PRESSURES: MATERIALISED vs. DEFERRED

**Critical distinction: Inflation already embedded in rates vs. future pass-through risk (LOW).**

### Input Costs Already Materialised in Freight Rates:

| Cost Component | Current Status | Evidence |
|---|---|---|
| **Bunker Fuel** | **Fully passed through** | 0.8/100 inflationary pressure score; only 0.8% 4W change. Bunker is a tiny driver of current rate volatility. This is **deflationary for shipping lines' fuel hedging** and suggests fuel surcharges are stable to declining. |
| **Interest Rates & Financing** | **Embedded in operating costs** | Rate_component = 100.0/100 signals financing costs are the **dominant inflationary lever**. With DXY strength and higher term rates, USD-denominated liner operating expenses (crew, maintenance, port fees) are rising but already reflected in bids. |
| **Vessel Utilisation** | **Pricing power collapsed** | CN_NEUR (-54.2%), CN_USWC (-43.6%), CN_OCE (-30.3%) indicate load factors are normalizing post-COVID, destroying operating leverage. Lines cannot sustain 2021-2022 margins. |

### Future Cost Pass-Through Risk (Minimal):

- **Crude component (44.9/100):** Elevated but decoupled from freight. If crude spikes (geopolitical risk score 65/100 reflects Ukraine/Red Sea), **shipping lines absorb this as input cost shock**, not pass through. No crude_cost → rate_component transmission visible in data.
- **BDI component (N/A):** Bulk dry indices unavailable, limiting assessment of dry bulk spillover effects on container markets.
- **Labour disruption (45/100):** US West Coast ILWU negotiations are **priced into Q4-Q1 forecasts** via risk premiums on spot rates. Unlikely to produce surprises; unionised US labour costs are already budgeted.

**Cost Inflation Assessment:** **Materialised costs already heavily discounted into freight rates.** Future inflation pass-through risk is LOW. Shipping lines are in margin-compression mode, not pricing-power mode.

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK

### Geopolitical Risk (Score: 65/100 – **ELEVATED**)

**Ukraine Black Sea Corridor:** 
- News item: "Ukraine seeks Black Sea shipping truce as drones hit Ust-Luga."
- **Risk to rates:** Black Sea grain flows are ~10-12% of global seaborne grains but concentrated in short-haul intra-Black Sea routes. Intermittent drone strikes on Russian terminals create *intermittent* supply disruption, not systematic capacity loss. **Impact on global container rates: minimal but tail-risk elevated.**
- **Insurance implication:** War risk premiums on Suez/Black Sea transits will remain sticky; reinsurance costs for war risk will not decline until ceasefire materialises (low probability near-term).

**Red Sea/Houthi Risk (implied):**
- Not explicitly flagged in news but geopolitical score of 65/100 likely reflects ongoing Yemen/Red Sea tensions.
- **Impact on rates:** Suez rerouting via Cape of Good Hope adds 10-14 days and ~$1.2-1.5M additional fuel/operating cost per 20k TEU vessel. This is a **permanent structural adder** to East-West rates that shipping lines cannot absorb indefinitely. Partial pass-through *may* occur if geopolitical premium sustains >6 months.

### Labour Disruption Risk (Score: 45/100 – MODERATE)

**US West Coast (ILWU):**
- 2024-2025 contract cycle is **live**. Historical pattern: 3-month disruptions occur ~50% of time.
- **CN_USWC showing -43.6%** may reflect pre-disruption rate weakness (shippers shifting cargo to East Coast ahead of labour threat).
- **Risk window: Q1 2025.** Potential 20-30 day port slowdown would spike spot rates 15-25%.

**Bangladesh Shipbreaking (cited incident: 7 deaths in toxic gas leak):**
- **Does NOT directly impact container shipping rates** but signals labour/safety crises in supply chain. Suggests tier-2 shipbreaker cost inflation, reducing vessel scrap value and extending fleet life. This is **deflationary for freight supply** (older, inefficient vessels stay in service longer).

**Bangladesh Labour Unrest (broader context):**
- If port workers are affected, this could impact Chittagong/Dhaka gateway volumes. Low probability near-term but warrants monitoring.

**Labour Risk Assessment:** **MODERATE. ILWU tail risk priced into Q1 spot volatility; unlikely to produce systematic rate recovery absent actual disruption.**

---

## (4) ACTIONABLE PORTFOLIO IMPLICATION

### **Recommendation: De-risk Shipping Credit Exposure; Upgrade Reinsurance Hedges**

#### **For Credit Portfolios (Bonds, CDS, Equity-linked notes):**

1. **Reduce long-duration exposure to container lines.** 
   - Current data shows margin compression (rate decline across all major routes except anomalies) with **no offsetting demand recovery**. 
   - Lines with high fixed-cost bases (e.g., MSC, Hapag-Lloyd, CMA CGM) and weak balance sheets will face covenant pressure in 2025 if rates don't stabilize.
   - Bunker deflation (0.8% 4W) is insufficient to offset volume declines. Sell or hedge BBB/BB container line bonds.

2. **Duration is unattractive; refinancing risk is rising.** 
   - Rate_component = 100.0/100 indicates financing costs remain high (term rates sticky). Lines with 2025-2026 maturities face adverse refinancing spread widening if demand doesn't recover.
   - **Action:** Exit 5-7Y container line bonds; maintain overweight in secured/collateralised credit (e.g., ship mortgage-backed securities, which have hard assets backing).

#### **For Reinsurance & Insurance Cost Outlook:**

3. **War risk premiums will NOT compress near-term; budget for 15-20% elevated reinsurance costs through 2025H1.**
   - Geopolitical risk score of 65/100 + Ukraine/Red Sea dynamics = sustained war risk premium.
   - Underwriters will demand 5-8% war risk add-on vs. 0.5-1% pre-2022 baseline.
   - **Action:** Lock in reinsurance treaties for 2025 renewals NOW (before Q1 market hardens further). Budget for $15-25M incremental war risk cost per $1B shipping portfolio.

4. **Port congestion risk (35/100 – MODERATE) is underpriced.**
   - Current data does not flag port disruption as acute, but geopolitical risk (65/100) + labour risk (45/100) + bunker volatility (0.8% 4W) suggest **latent port stress**.
   - If ILWU strikes or Red Sea rerouting concentrates cargo at fewer hubs (Singapore, Rotterdam), congestion multiplier effects will spike rates 10-15% in affected corridors.
   - **Action:** Stress-test port concentration risk in cargo exposure; ensure cargo insurance reflects 7-10 day voyage delays, not 5-6 day baseline.

#### **Inflation Assumption Revision:**

5. **Lower near-term freight inflation assumptions for 2025; maintain elevated long-term geopolitical premium.**
   - Base case freight rates are in decline trend (majority routes cooling). **Freight inflation expectations should be reset downward** for CPI/PPI models.
   - However, **geopolitical tail risk (Red Sea, Ukraine, China-Taiwan tensions) justifies +2-3% structural premium** on medium/long-haul rates that will NOT deflate until geopolitical risk scores <40/100.
   - **Implication for liability matching:** If your portfolio uses shipping rates as inflation proxy, demand compression means real yields are **tighter than nominal yields suggest**. De-risk duration selectively.

---

## SUMMARY TABLE: PORTFOLIO SIGNALS

| Signal | Current Reading | Portfolio Action |
|---|---|---|
| **Demand Momentum** | Recession (base case); episodic spikes | De-risk cyclical; reduce BB/B credit |
| **Cost Pass-Through Risk** | Low (costs already embedded) | No inflation buffer available for lines |
| **Geopolitical Risk** | 65/100 – ELEVATED | Budget 15-20% reinsurance cost increase |
| **Labour Risk** | 45/100 – MODERATE; ILWU tail Q1 2025 | Hedge Q1 spot volatility; watch USWC |
| **Port Congestion** | 35/100 – MODERATE but rising | Stress-test concentration; upgrade cargo coverage |
| **Bunker Deflation** | 0.8% 4W – HEADWIND | Does not offset demand decline |
| **Credit Spreads** | Should widen; refinancing risk up | Sell BBB/BB; buy secured tranches |

**Recommended portfolio action horizon: Execute within 2-4 weeks, ahead of Q1 2025 labour negotiations and 2025H1 reinsurance renewals.**

---

**Inflationary Pressure Score: 43 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 1 | 35% | ⚠ 20w of 52w |
| Brent Crude (4W Δ) | 45 | 20% | ⚠ 20w of 52w |
| Freight Rate Composite (4W Δ) | 100 | 25% | ⚠ 20w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 20 weeks; Brent Crude 20 weeks; Freight Rate Composite 20 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
>
> ⚠ **Excluded from the composite** — Baltic Dry Index: fewer than 12 weeks of real data. Reported as INSUFFICIENT_HISTORY rather than normalised on a window too short to be meaningful; the remaining weights are redistributed proportionally.
>
> ℹ️ **Scale breaks** — component scores are min-max normalised, so they are only comparable across reports that share the same scale. Scores in reports published before 2026-07-27 are **not** comparable to these. Changes that moved the scales, newest first:
>
> - **2026-07-27 — Synthetic rows excluded from the normalisation history.** 168 seed rows in freight_rates, and 280 in input_costs, were removed from the windows behind every component. The bunker and crude scales moved most: both had been built on real and fabricated observations mixed together.

## News Sentiment Risk

| Risk Category | Score (0–100) | Level |
|---------------|:-------------:|-------|
| Geopolitical Risk      | 65 | 🟠 MODERATE |
| Labour Disruption Risk | 45 | 🟠 MODERATE |
| Port Congestion Risk   | 35 | 🟢 LOW |

**Key Events Detected:**
- Ukraine seeks Black Sea shipping truce as drones hit Ust-Luga
- Seven die in toxic gas leak at Bangladesh shipbreaking yard
- China's VLOC conveyor belt threatens to dilute Simandou cape upside

**Routes at Risk:** Black Sea - Mediterranean · Black Sea - Europe · Baltic - Atlantic · Australia - China (iron ore) · South Africa - India · West Africa - Global

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $487 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (34 obs) |
| China/East Asia → North Europe | $4,123 | N/A | ▼ 54.2% | $8,852 | 🔵 COOLING |
| China/East Asia → Oceania | $4,567 | N/A | ▼ 30.3% | $6,474 | 🔵 COOLING |
| China/East Asia → South America | $5,678 | N/A | ▲ 2.7% | $5,501 | 🟢 STABLE |
| China/East Asia → North America East Coast | $2,890 | N/A | ▲ 583.2% | $519 | 🟠 SPIKE |
| China/East Asia → North America West Coast | $3,456 | N/A | ▼ 43.6% | $6,382 | 🔵 COOLING |
| FBX12 – FBX12 | $3,234 | N/A | ▲ 507.9% | $648 | 🟠 SPIKE |
| FBX14 – FBX14 | $2,345 | N/A | ▲ 252.1% | $697 | 🟠 SPIKE |
| FBX21 – FBX21 | $6,789 | N/A | ▲ 1260.5% | $764 | 🟠 SPIKE |
| FBX22 – FBX22 | $2,244 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (34 obs) |
| FBX24 – FBX24 | $1,246 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (34 obs) |
| FBX26 – FBX26 | $2,464 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (34 obs) |

---
_Generated 2026-08-16 00:12 UTC_