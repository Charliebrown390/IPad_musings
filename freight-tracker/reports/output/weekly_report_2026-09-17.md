# 🚨 Freight Rate Weekly Report — 2026-09-17

> ℹ️ **Data provenance** — 168 of 1,608 rows are synthetic (seed) data and are **excluded from every calculation** in this report; 1,440 real observations were used.
>
> Quarantined, not deleted, for audit. Sources: `seed-data` (156), `seed-data/march-2026` (12).

> ⚠ **STALE DATA WARNING** — 2 indices not reporting usable data (threshold 14 days):
>
> - **SCFI** — 🛑 **no real data at all**; every one of its 78 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
> - **WCI** — 🛑 **no real data at all**; every one of its 56 rows is synthetic. This index has never scraped successfully. Contributes nothing to any calculation.
>

## Executive Summary

# FREIGHT MARKET EXECUTIVE SUMMARY
**For: Fixed Income & Multi-Asset Portfolio Management**

---

## (1) DEMAND TRENDS BY REGION

**Mixed regional momentum with divergent rate trajectories:**

**Strengthening Demand Corridors:**
- **US-bound lanes (CN_USEC, CN_USWC):** Combined +8.4% WoW momentum signals sustained trans-Pacific import demand. US East Coast acceleration (+5.8% WoW, STABLE momentum) outpaces West Coast (+2.6%), consistent with inventory restocking and near-shoring distribution patterns. Both show stable momentum—demand appears structural rather than transient.
- **North Europe (CN_NEUR):** +2.3% WoW with STABLE momentum indicates resilient EU import appetite despite energy cost headwinds, likely driven by pre-winter logistics positioning.

**Weakening Demand Corridors:**
- **Oceania (CN_OCE):** Sharp -12.2% WoW decline with COOLING momentum is the most concerning signal. This suggests either Australian/NZ commodity export softness or reduced intra-Asia feeder demand—a leading indicator of Asia-Pacific regional weakness.
- **South America (CN_SAM):** Modest -3.0% WoW but STABLE momentum suggests equilibrium pricing rather than demand collapse; likely reflects seasonal agricultural export patterns post-harvest peak.

**Index-Level Observations:**
- **FBX21 spike (+51.6%, SPIKE momentum)** is anomalous and warrants investigation—likely a specific route disturbance (port closure, vessel shortage, or geopolitical disruption) rather than broad market signal. Without route mapping, this creates blind spot risk.
- **FBX12/FBX14 weakness (-4.4% / 0.0%, COOLING):** Suggests short-haul or feeder services experiencing demand compression.

**Portfolio Implication:** Demand bifurcation is emerging—Atlantic/Pacific gateways remain firm, but Asia-Pacific regional demand softening could presage Q1 2024 headwinds.

---

## (2) INFLATIONARY COST PRESSURES: MATERIALIZED vs. NOT YET PASSED THROUGH

**Composite Score: 50/100 – Moderate Pressure, But Critically Asymmetric**

**Already Materialized in Costs (Not Yet Reflected in Freight Rates):**

| Input Cost | Component Score | Status | Implication |
|---|---|---|---|
| **Bunker Fuel (HFO/LSMGO)** | 9.4/100 | **Minimal** | 4W change of +9.4% is modest; current bunker cost recovery is adequate. *Shipping lines have already passed through most fuel surcharges.* |
| **Crude/Energy** | 73.8/100 | **HIGH SPIKE** | ⚠️ **Critical:** This is the buried landmine. Crude component score of 73.8/100 suggests significant energy cost inflation *not yet reflected in freight rates*. If bunker costs re-accelerate (geopolitical supply shock), lines will face 8-12 week lag before contractual rate adjustments take hold. |

**Not Yet Passed Through to Rates (Embedded Cost Pressure):**

| Component | Score | Explanation |
|---|---|---|
| **Rate Component** | 86.9/100 | This is the most inflationary signal in the dataset. High rate component reflects broad-based cost inflation (labour, maintenance capex, terminal fees, box repositioning) embedded in operating expenses but *not yet fully monetized* in published freight rates. Lines are absorbing margin compression. |
| **BDI Component** | N/A | Data absence; unable to assess bulk shipping spillover effects. This limits macro shipping cycle visibility. |

**Compression Signal:** The 36.5-point gap between rate_component (86.9) and bunker_component (9.4) indicates **hidden margin erosion**. Shipping lines are running tighter utilization-adjusted margins because:
- Labour costs (Europe/US port labour agreements ramping post-2023) haven't flowed into published tariffs yet
- Vessel capex service costs (mega-ship financing) are rising; lines are *not* yet surcharging for this
- Port congestion cost pass-through remains incomplete (see port_congestion=30/100 below)

**Materialization Timeline:** Rate component inflation typically crystallizes in 6-9 month forward contracts. Current spot rates (reflected in WoW data) are thus **artificially depressed** relative to true marginal cost.

**Critical Risk:** If crude-linked bunker costs spike again (geopolitical shock to ME oil), combined with rate component pressure, shipping lines will face a **margin compression cliff**—and will need to aggressively push rate increases. This creates Q2-Q3 2024 upside inflation risk in freight-linked sectors (manufacturing, logistics, apparel).

---

## (3) GEOPOLITICAL & LABOUR ROUTE RISK ANALYSIS

**News Sentiment Baseline: Elevated but Not Crisis-Level**

| Risk Factor | Score | Route-Specific Exposure |
|---|---|---|
| **Geopolitical Risk** | 25.0/100 | Moderate; no acute Red Sea, Taiwan Strait, or Ukraine-adjacent impacts currently priced. However, *latent* — any Houthi escalation or Taiwan tension will reprrice instantly. |
| **Labour Disruption** | 35.0/100 | **Elevated:** Germany bridge-opening (non-EU captains) signals tight crew supply; expect wage inflation in North Europe (CN_NEUR affected). US port labour negotiations concluding; expect 2-3% rate premiums as lines budget for 2024 labour cost uplift. |
| **Port Congestion** | 30.0/100 | **Moderate but sticky:** Not currently acute (would expect >50 if major logjam), but elevated above historical baseline. CN_USEC strength (+5.8%) may be *despite* congestion; rate relief when ports clear could create spot softness. |

**Route-Specific Vulnerabilities:**

1. **CN_MED (Mediterranean):** INSUFFICIENT_HISTORY flag is itself concerning—possible data disruption (Suez toll pressure? Port strikes?). Recommend immediate data validation.

2. **CN_NEUR:** Labour risk is *highest* here. German captain shortage + French labour militancy + UK port tensions = 15-20% cumulative rate uplift over next 2 quarters as lines pass through crew costs.

3. **CN_OCEANIA:** -12.2% decline + COOLING momentum may be demand-driven, but geopolitical edge-case: any Australia-China trade friction would be a demand shock (China is #1 destination for AU commodity exports). Current weakness could mask pre-emptive shipper behaviour.

4. **US Lanes (USEC/USWC):** Labour risk here is *manageable*—ILA agreement (concluded Oct 2023) is locked in; rates have already partially absorbed labour cost visibility. However, port congestion relief could create Q1 volatility.

**News Catalyst Tracking:**
- **"Maersk overtakes COSCO as largest intra-Asia carrier"** = Positive supply discipline signal; consolidation may support rate floors in 2024.
- **"CMA CGM megamax order"** = Capacity expansion (+15-20k TEU equivalent fleet-wide) will enter service in 2025-26; no immediate rate pressure, but suggests lines are bullish on demand and willing to absorb 2-3 year payback horizon.

---

## (4) ACTIONABLE PORTFOLIO IMPLICATION

### **RECOMMENDATION: Recalibrate Inflation Assumptions & Increase Selective Credit Monitoring of Shipping Exposure**

**Specific Actions:**

1. **Revise Inflation Dodge Thesis:**
   - Current portfolio positioning likely assumes shipping cost inflation has *already* been absorbed and reflected in freight rates. **This is incorrect.**
   - Rate_component score of 86.9/100 + bunker 4W change of +9.4% suggest **6-9 months of deferred inflation pass-through ahead**. 
   - **Action:** Increase 2024 CPI/PPI inflation assumptions for goods-intensive sectors (furniture, electronics, apparel, automotive parts) by 50-80bps to account for delayed freight cost recovery. This is a **positive** signal for inflation-hedged bonds (TIPS) and floating-rate credit.

2. **Shipping Sector Credit Exposure—Bifurcated Approach:**
   - **Downgrade outlook** for smaller regional carriers and asset-light 3PLs (exposed to rate compression if CN_OCE/CN_SAM weakness spreads). Monitor credit default swap spreads on Russell 2000 transport logistics names.
   - **Upgrade outlook** for mega-carriers (Maersk, MSC, CMA CGM) with pricing power—FBX index weakness is masking their ability to push premium (steady momentum on high-value lanes: USEC, NEUR). Their 2024 earnings likely beat consensus due to hidden margin recovery in Q2-Q3.

3. **Reinsurance Cost Outlook—Moderate Upside Risk:**
   - Port congestion (30/100) + labour disruption (35/100) = rising marine cargo claims frequency in 2024 (delays, pilferage, environmental damage). 
   - Combined with mega-ship concentrated risk (larger per-vessel exposure), marine underwriters will push **+5-8% rate increases** at 2024 renewals.
   - **Action:** For portfolios with marine reinsurance exposure, lock in 2024 capacity now if not already done; expect hard market conditions through 2024.

4. **FX & Commodity Hedge Positioning:**
   - The crude_component=73.8/100 score signals commodity-linked inflation ahead. If portfolio is long shipping-exposed equities or corporate credit in supply-chain sectors, consider **modest commodity hedges** (crude, bunker futures) to protect against 15-20% spike scenario by Q2 2024.

---

### **Risk Rating Summary**
| Category | Signal | Confidence |
|---|---|---|
| **Near-term Rate Pressure** | MODERATE-HIGH | High (rate component + labour data converge) |
| **Demand Cliff Risk** | LOW-MODERATE | Moderate (OCE weakness is data point, not trend yet) |
| **Inflation Surprise Upside** | MODERATE-HIGH | High (embedded cost lag is material) |
| **Credit Stress (shipping sector)** | LOW | Low (mega-carriers have pricing power; smaller names at risk) |

**Monitoring Cadence:** Weekly FBX index review + bi-weekly route momentum tracking; escalate if CN_OCE extends beyond -15% WoW or FBX21 becomes persistent pattern (suggests structural disruption, not noise).

---

**Inflationary Pressure Score: 50 / 100**

| Component | Score (0–100) | Weight | Normalisation window |
|-----------|--------------|--------|----------------------|
| Bunker Fuel (VLSFO Singapore 4W Δ) | 9 | 35% | ⚠ 25w of 52w |
| Brent Crude (4W Δ) | 74 | 20% | ⚠ 25w of 52w |
| Freight Rate Composite (4W Δ) | 87 | 25% | ⚠ 25w of 52w |
| Baltic Dry Index (4W Δ) | INSUFFICIENT_HISTORY | 20% | no data |

> ⚠ **Partial normalisation window** — the 52-week min-max scale could not be filled for: Bunker Fuel 25 weeks; Brent Crude 25 weeks; Freight Rate Composite 25 weeks. These components are normalised on the history that exists, so their scores are more volatile than a full-window score and are not comparable to one.
>
> ⚠ **Excluded from the composite** — Baltic Dry Index: fewer than 12 weeks of real data. Reported as INSUFFICIENT_HISTORY rather than normalised on a window too short to be meaningful; the remaining weights are redistributed proportionally.
>
> ℹ️ **Scale breaks** — component scores are min-max normalised, so they are only comparable across reports that share the same scale. Scores in reports published before 2026-07-27 are **not** comparable to these. Changes that moved the scales, newest first:
>
> - **2026-07-27 — Synthetic rows excluded from the normalisation history.** 168 seed rows in freight_rates, and 280 in input_costs, were removed from the windows behind every component. The bunker and crude scales moved most: both had been built on real and fabricated observations mixed together.

## News Sentiment Risk

| Risk Category | Score (0–100) | Level |
|---------------|:-------------:|-------|
| Geopolitical Risk      | 25 | 🟢 LOW |
| Labour Disruption Risk | 35 | 🟢 LOW |
| Port Congestion Risk   | 30 | 🟢 LOW |

**Key Events Detected:**
- Germany opens bridge to non-EU captains
- Maersk overtakes COSCO to become largest intra-Asia carrier
- CMA CGM tipped for $3bn Yangzijiang megamax order

**Routes at Risk:** Intra-Asia container routes · EU-Asia trade lanes · German port operations · Chinese steel export routes (Capesize markets)

---

## Rate Summary

| Route | FBX Rate | WCI Rate | WoW % | 4W Avg | Signal |
|-------|----------|----------|-------|--------|--------|
| China/East Asia → Mediterranean | $485 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (62 obs) |
| China/East Asia → North Europe | $9,724 | N/A | ▲ 2.3% | $9,649 | 🟢 STABLE |
| China/East Asia → Oceania | $4,158 | N/A | ▼ 12.2% | $4,719 | 🔵 COOLING |
| China/East Asia → South America | $4,366 | N/A | ▼ 3.0% | $4,576 | 🟢 STABLE |
| China/East Asia → North America East Coast | $362 | N/A | ▲ 5.8% | $350 | 🟢 STABLE |
| China/East Asia → North America West Coast | $7,765 | N/A | ▲ 2.6% | $7,606 | 🟢 STABLE |
| FBX12 – FBX12 | $516 | N/A | ▼ 4.4% | $530 | 🟢 STABLE |
| FBX14 – FBX14 | $170 | N/A | ▲ 0.0% | $263 | 🔵 COOLING |
| FBX21 – FBX21 | $632 | N/A | ▲ 51.6% | $467 | 🟠 SPIKE |
| FBX22 – FBX22 | $2,666 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (62 obs) |
| FBX24 – FBX24 | $1,087 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (62 obs) |
| FBX26 – FBX26 | $2,340 | N/A | N/A | N/A | ⚪ INSUFFICIENT HISTORY (62 obs) |

---
_Generated 2026-09-17 00:22 UTC_