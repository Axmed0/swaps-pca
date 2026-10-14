# PCA on USD, EUR and GBP OIS swap curves

USD SOFR, EUR ESTR and GBP SONIA par swap curves, 1y to 30y, daily to April 2026. Python.

Methods follow the practitioner research collected in [yieldcurvemonkey/Curvy-CUSIPs/research/PCA](https://github.com/yieldcurvemonkey/Curvy-CUSIPs/tree/main/research/PCA), mainly Salomon Smith Barney's "Principles of Principal Components" (2000), with the residual approach from Credit Suisse's "PCA Unleashed" (2012) and Standard Chartered's swaps relative-value tool (2013).

## Summary

- Three factors explain 99.5% to 99.7% of daily moves in each curve, and the three currencies have almost identical factor shapes. Level explains 87% to 88%, slope 10% to 11%, curvature 1.0% to 1.4%.
- Across currencies, one global factor explains 69.6% of weekly moves in the 27 rates combined. The second (12.9%) is USD against GBP. EUR needs a fourth factor of its own: two global factors explain 72% of EUR curve variance but 85% to 87% of USD and GBP.
- Same-day correlations across currencies are understated: the USD 10y move today has a 0.14 correlation with tomorrow's EUR 10y move, against 0.01 the other way. USD marks later in the day, so cross-currency PCA has to use weekly data.
- PCA fly weights from daily changes are the best hedge out of sample. They cut the share of fly variance explained by level and slope to 1% to 8%, against 7% to 34% for 50/50 weights. Weights from yield levels hedge worse (3% to 19%).
- Salomon's butterfly trading rule does not survive on these curves. Pooled over six flies, PCA-level trades won 70% of the time but averaged -0.24bp, because the 36% of trades that never reverted lost 5.7bp on average. Trades entered in 2022 explain the losses. Outside 2022 the average is +0.42bp a trade.

## Data

| | Start | End | Days |
|---|---|---|---|
| USD SOFR | 17 Apr 2018 | 27 Apr 2026 | 2,007 |
| EUR ESTR | 1 Aug 2019 | 27 Apr 2026 | 1,725 |
| GBP SONIA | 26 Jun 2014 | 17 Apr 2026 | 2,985 |

- Daily par swap rates at 29 tenors from 1 week to 50 years, supplied as pickled pandas DataFrames. Source: Bloomberg. The analysis uses the nine tenors 1y, 2y, 3y, 5y, 7y, 10y, 15y, 20y and 30y.
- No gaps longer than five calendar days and no stale rows. The largest daily moves line up with known events: USD 1y -79.5bp on 13 March 2023, EUR 1y -41.2bp on 15 March 2023, GBP 1y +72.7bp on 26 September 2022.
- Cross-check against the Bank of England OIS spot curve (fitted zero-coupon rates, 2,599 common days): GBP par rates sit 0.5bp to 2.4bp above the BoE curve on average at 2y, 5y, 10y and 25y, and daily changes have a 0.92 to 0.95 correlation. Par against zero rates and different marking times explain the gap.
- Loading the pickles uses a restricted unpickler that only allows pandas and numpy classes (`src/load_data.py`).

## 1. The three curves have the same three factors

![loadings](output/fig1_loadings_by_ccy.png)

| | Level | Slope | Curvature | Top 3 | Daily std 2y / 10y / 30y (bp) |
|---|---|---|---|---|---|
| USD | 87.1% | 11.2% | 1.4% | 99.7% | 5.8 / 5.7 / 5.2 |
| EUR | 87.9% | 10.3% | 1.4% | 99.5% | 4.5 / 4.6 / 4.3 |
| GBP | 88.4% | 10.2% | 1.0% | 99.6% | 4.7 / 5.2 / 5.2 |

- Level peaks at 5y in USD and EUR (0.38) and fades to 0.30 at 30y. In GBP it stays at 0.34 to 0.36 from 5y to 30y. The GBP long end moves more with the rest of the curve than the USD or EUR long end does.
- Slope pivots near 7y in all three. Curvature is the 1y and 30y against the 5y belly.

## 2. The slope share doubles in hiking cycles

![rolling slope share](output/fig2_rolling_slope_share.png)

- Rolling one-year PC2 share peaked at 19.7% in GBP (window to 9 November 2021), 16.5% in EUR (28 February 2022) and 12.7% in USD (3 March 2022), against medians of 6.5%, 8.6% and 8.0%.
- GBP peaked first, in November 2021. EUR and USD peaked within a week of each other at the end of February 2022.
- The latest windows (April 2026) have PC2 at 9.0% (USD), 11.5% (EUR) and 11.4% (GBP), all above their medians.

## 3. One global factor drives 70% of weekly moves

![global factors](output/fig3_global_factors.png)

Weekly (Wednesday to Wednesday) changes in all 27 rates, 1 August 2019 to 17 April 2026, 350 weeks.

| Global factor | Share | What it is |
|---|---|---|
| G1 | 69.6% | All rates up together. GBP loadings are the largest (0.17 to 0.24), EUR the smallest (0.11 to 0.18). |
| G2 | 12.9% | USD up, GBP down (USD 2y +0.34, GBP 10y -0.23). EUR loads near zero. |
| G3 | 7.9% | Global slope: front ends up, long ends down in all three. |
| G4 | 5.2% | EUR level against the rest (EUR +0.23 to +0.31). |

Share of each curve's weekly variance explained by the first k global factors:

| | k = 1 | k = 2 | k = 3 | k = 4 |
|---|---|---|---|---|
| USD | 63.8% | 84.6% | 93.9% | 95.3% |
| EUR | 70.9% | 71.7% | 79.1% | 94.9% |
| GBP | 74.0% | 87.0% | 93.9% | 96.1% |

- 10y correlations: USD-EUR 0.65 daily and 0.73 weekly, USD-GBP 0.63 and 0.67, EUR-GBP 0.78 and 0.81. The daily figures are understated. USD today against EUR tomorrow is 0.14, against GBP tomorrow 0.15, while EUR today against USD tomorrow is 0.01. USD marks after the European close, so the afternoon's US move only reaches EUR and GBP rates the next day.
- Global level alone explains 74% of GBP curve variance. The first two global factors explain only 72% of EUR: EUR has its own level factor (G4), consistent with the ECB moving on a different timetable from the Fed and the BoE.

## 4. Weights from daily changes give the best hedge

![hedge test](output/fig4_hedge_test.png)

Method: at each month end, estimate the fly weights on the trailing two years, then hold them through the next month (Salomon Part I). Three weightings: 50/50 (body minus half of each wing), PCA on yield changes and PCA on yield levels. For PCA weights the fly is the third principal component of its three legs, scaled to a body weight of 1, which makes it uncorrelated with the first two. Hedge quality is the R-squared of daily out-of-sample fly changes on the average move across the curve (level) and the 2s30s change (slope).

| | 50/50 | PCA changes | PCA levels |
|---|---|---|---|
| USD 2s5s10s | 21.7% | 2.3% | 18.7% |
| USD 5s10s30s | 34.0% | 4.6% | 14.4% |
| EUR 2s5s10s | 29.0% | 6.1% | 14.3% |
| EUR 5s10s30s | 17.9% | 7.7% | 11.1% |
| GBP 2s5s10s | 20.0% | 1.3% | 3.7% |
| GBP 5s10s30s | 6.6% | 3.0% | 2.6% |

- Weights from changes give the lowest level and slope exposure in five of six flies and are within 0.4 points of the best in the sixth. That matches Salomon's advice to hedge with change-based components.
- Every 50/50 fly moves with the level of rates: +0.02bp to +0.10bp of fly per bp of level move. A 50/50 fly is partly a duration trade.

## 5. The Salomon butterfly rule does not pay on these curves

![backtest](output/fig5_salomon_backtest.png)

Rule (Salomon Part II, base case): PCA weights from yield levels over the trailing two years. Enter when the fly is above its 97th or below its 3rd percentile over that window, receiving the body when it is high (body cheap) and paying it when low. Exit when it is back inside the 90th/10th percentile, or after 60 trading days. Weights and the reference window stay fixed for the life of the trade, and nothing uses data after the entry date. P&L is in bp of fly with the body DV01 set to 1, before costs.

| | Trades | Hit rate | Avg (bp) | Total (bp) | Worst (bp) | Timed out | Sharpe |
|---|---|---|---|---|---|---|---|
| USD 2s5s10s | 18 | 50% | -1.94 | -34.9 | -27.1 | 10 | -0.46 |
| USD 5s10s30s | 19 | 79% | +0.86 | +16.4 | -10.6 | 5 | 0.38 |
| EUR 2s5s10s | 10 | 50% | -5.69 | -56.9 | -33.5 | 5 | -0.96 |
| EUR 5s10s30s | 19 | 68% | -0.44 | -8.4 | -12.5 | 7 | -0.14 |
| GBP 2s5s10s | 31 | 81% | +0.84 | +26.1 | -10.9 | 8 | 0.28 |
| GBP 5s10s30s | 22 | 73% | +1.30 | +28.7 | -8.6 | 8 | 0.33 |

Pooled over all six flies:

| Weights | Trades | Hit rate | Avg (bp) | Avg if reverted (bp) | Avg if timed out (bp) | Timed out |
|---|---|---|---|---|---|---|
| PCA levels | 119 | 70% | -0.24 | +2.86 | -5.73 | 36% |
| PCA changes | 112 | 65% | -0.52 | +2.78 | -5.64 | 39% |
| 50/50 | 112 | 80% | +1.13 | +2.63 | -3.14 | 26% |

- The payoff is many small wins and a few large losses. Trades that revert make about 3bp. Trades that do not revert lose about twice that.
- 2022 explains the losses. The 31 PCA-level trades entered in 2022 averaged -2.13bp. USD and EUR 2s5s10s lost 38.9bp and 63.4bp on trades opened that year, more than their full-sample totals. Those were pay-body trades, and the 5y kept richening against the wings as hikes were priced. Outside 2022 the average trade made +0.42bp.
- The 50/50 version looks better (+1.13bp a trade), but section 4 shows those flies carry 7% to 34% level and slope exposure. Part of that P&L is directional.
- Salomon's alternatives do not rescue it. Across start/exit pairs of 3/10, 3/30 and 10/30 and holding limits of 60 and 120 days, the median Sharpe across the six flies is between -0.40 and 0.07, and at most three of six flies are positive in any setting.

## 6. Rich/cheap residuals are small and short-lived

![residuals](output/fig6_residual_zscores.png)

Method (CS and Standard Chartered): each day, fit three principal components to the trailing year of yield levels and take each tenor's residual (actual minus three-factor fit). A z-score uses the residual's own trailing year.

- Residuals have a standard deviation of 0.4bp to 1.9bp and half-lives of 6 to 26 trading days.
- On the last date in the data no tenor is more than 1.5 standard deviations from fair value (largest: EUR 1y +1.49, USD 5y -1.41). At least one tenor sits beyond ±2 on 26% to 32% of days, so a 2-sigma residual is common.
- These are April 2026 readings and say nothing about the curve today.

## Limitations

- Data ends in April 2026 and the source is not documented in this repo yet.
- SOFR swaps traded thinly in 2018 and ESTR was first published in October 2019, so the earliest USD and EUR data may be proxied or illiquid.
- Fly P&L is before bid/offer on three legs in and out. The sample has 10 to 31 trades per fly, too few for confident Sharpe ratios.
- Fly weights and both backtest rules were fixed before running them. The six-setting grid in section 5 is the only parameter search, and it is reported in full.

## Reproduce

```bash
pip install -r requirements.txt
python src/load_data.py usd_sofr_curve.p eur_estr_curve.p gbp_sonia_curve.p   # pickles -> data/*.csv
python src/swaps_pca.py      # charts, trade list and output/results.json
python src/validate_gbp.py   # optional cross-check against the Bank of England curve
```

Every number in this note is in `output/results.json`, `output/validation.json` or `output/salomon_trades.csv`.

References (all in the Curvy-CUSIPs research/PCA folder)

- Baygun, Showers and Cherpelis, "Principles of Principal Components: A Fresh Look at Risk, Hedging, and Relative Value", Salomon Smith Barney, January 2000.
- Pelata, Giannopoulos and Haworth, "PCA Unleashed", Credit Suisse Fixed Income Research, October 2012.
- Lee, Davies and Fernandez, "Introducing a relative-value tool for swaps", Standard Chartered Rates Alert, August 2013.
