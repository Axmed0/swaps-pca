"""PCA on USD SOFR, EUR ESTR and GBP SONIA swap curves.

Methods follow the practitioner literature collected in yieldcurvemonkey/Curvy-CUSIPs (research/PCA),
mainly Salomon Smith Barney, "Principles of Principal Components" (Baygun, Showers, Cherpelis, 2000):
  Part I   PCA on daily changes as risk factors; PCA-weighted butterflies as curve-neutral hedges.
  Part II  Butterfly relative value: PCA weights from yield levels, entry when the PCA fly is at an
           extreme percentile of its rolling history, exit on partial reversion or after a max holding period.
and the residual "fair value" approach in Credit Suisse, "PCA Unleashed" (2012) and Standard Chartered,
"Introducing a relative-value tool for swaps" (2013).

Sections
  1. Single-currency PCA on daily changes (full sample, rolling one-year)
  2. Global PCA on weekly changes of all three curves
  3. Out-of-sample hedge test: levels-PCA, changes-PCA and 50/50 fly weights
  4. Salomon butterfly backtest, fully out of sample
  5. Rolling 3-factor residuals (rich/cheap) on the last date in the data

Everything quoted in the README is written to output/results.json.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT / "data", ROOT / "output"
OUT.mkdir(exist_ok=True)

CCYS = ["USD", "EUR", "GBP"]
TENORS = ["1y", "2y", "3y", "5y", "7y", "10y", "15y", "20y", "30y"]
YRS = [1, 2, 3, 5, 7, 10, 15, 20, 30]
FLIES = [("2y", "5y", "10y"), ("5y", "10y", "30y")]       # fixed before running any backtest
ROLL = 252          # rolling PCA window for section 1 and residual window for section 5 (one year)
FLY_WIN = 504       # Salomon: two-year rolling window for fly weights and percentiles
ENTER, EXIT, MAX_HOLD = 0.97, 0.90, 60                    # Salomon base case: 3/10 percentiles, 60 days
GRID = [(0.97, 0.90), (0.97, 0.70), (0.90, 0.70)]         # Salomon's three best start/exit pairs
HOLDS = [60, 120]

SURFACE, INK, INK2, GRIDC = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"USD": "#2a78d6", "EUR": "#eb6834", "GBP": "#1baf7a"}
NEUTRAL = "#8f8e88"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRIDC, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.grid": True, "grid.color": GRIDC, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "lines.linewidth": 2, "legend.frameon": False,
})


def load():
    return {c: pd.read_csv(DATA / f"{c.lower()}_swap_curve.csv", index_col=0, parse_dates=True)[TENORS] * 100
            for c in CCYS}                                                       # percent -> bp


def pca(X):
    """Eigen-decomposition of the covariance of X (rows = dates). Sign convention: PC1 positive,
    PC2 positive at the short end, PC3 positive at the short end."""
    w, v = np.linalg.eigh(np.cov(np.asarray(X).T))
    o = np.argsort(w)[::-1]
    w, v = w[o], v[:, o]
    v = v * np.sign(v.sum(axis=0))
    for k in (1, 2):
        if v.shape[1] > k and v[0, k] < 0:
            v[:, k] *= -1
    return w, v


def fly_weights(Y, how):
    """Wing weights (wa, wc) for body - wa*short wing - wc*long wing.
    PCA: the fly is the third principal component of the three legs (Salomon), scaled to body = 1,
    which makes it uncorrelated with the first two components of those three yields."""
    if how == "50/50":
        return 0.5, 0.5
    X = Y if how == "PCA levels" else np.diff(Y, axis=0)
    w, v = np.linalg.eigh(np.cov(X.T))
    e3 = v[:, np.argmin(w)]
    return -e3[0] / e3[1], -e3[2] / e3[1]


def fly_name(f):
    return "s".join(x[:-1] for x in f) + "s"


def style_tenor_axis(ax):
    ax.set_xscale("log")
    ax.set_xticks(YRS, [str(y) for y in YRS])
    ax.minorticks_off()


def section1(C, res):
    res["single"] = {}
    loads = {}
    for c, df in C.items():
        d = df.diff().dropna()
        w, v = pca(d.values)
        loads[c] = v
        res["single"][c] = {
            "start": str(d.index[0].date()), "end": str(d.index[-1].date()), "n_days": len(d),
            "share_pct": [round(x, 1) for x in w[:4] / w.sum() * 100],
            "top3_pct": round(w[:3].sum() / w.sum() * 100, 1),
            "pc1": dict(zip(TENORS, np.round(v[:, 0], 2))), "pc2": dict(zip(TENORS, np.round(v[:, 1], 2))),
            "pc3": dict(zip(TENORS, np.round(v[:, 2], 2))),
            "daily_std_bp": d.std().round(2).to_dict(),
            "largest_day": {"date": str(d.abs().max(axis=1).idxmax().date()),
                            "tenor": d.loc[d.abs().max(axis=1).idxmax()].abs().idxmax(),
                            "bp": round(float(d.loc[d.abs().max(axis=1).idxmax()][d.loc[d.abs().max(axis=1).idxmax()].abs().idxmax()]), 1)},
        }
        # PC1 peak tenor
        res["single"][c]["pc1_peak_tenor"] = TENORS[int(np.argmax(v[:, 0]))]

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), sharey=True)
    for k, (ax, lab) in enumerate(zip(axes, ("PC1 level", "PC2 slope", "PC3 curvature"))):
        for c in CCYS:
            share = res["single"][c]["share_pct"][k]
            ax.plot(YRS, loads[c][:, k], color=COL[c], marker="o", markersize=4, label=f"{c} ({share:.1f}%)")
        ax.axhline(0, color=INK2, linewidth=0.8)
        style_tenor_axis(ax)
        ax.set_title(lab)
        ax.set_xlabel("Tenor (years, log scale)")
        ax.legend(loc="lower left", fontsize=8)
    axes[0].set_ylabel("Loading")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_loadings_by_ccy.png", dpi=160)
    plt.close(fig)

    # rolling one-year shares
    roll = {}
    for c, df in C.items():
        d = df.diff().dropna().values
        idx = df.diff().dropna().index
        rows = []
        for i in range(ROLL, len(d) + 1):
            w, _ = pca(d[i - ROLL:i])
            rows.append((idx[i - 1], w[0] / w.sum(), w[1] / w.sum()))
        roll[c] = pd.DataFrame(rows, columns=["date", "pc1", "pc2"]).set_index("date")
    res["rolling"] = {c: {"pc2_max_pct": round(r.pc2.max() * 100, 1), "pc2_max_date": str(r.pc2.idxmax().date()),
                          "pc2_median_pct": round(r.pc2.median() * 100, 1),
                          "pc1_min_pct": round(r.pc1.min() * 100, 1), "pc1_min_date": str(r.pc1.idxmin().date()),
                          "pc2_latest_pct": round(r.pc2.iloc[-1] * 100, 1)} for c, r in roll.items()}
    pd.concat({c: r for c, r in roll.items()}, axis=1, sort=True).to_csv(OUT / "rolling_shares.csv", float_format="%.4f")

    fig, ax = plt.subplots(figsize=(8, 3.8))
    for c in CCYS:
        ax.plot(roll[c].index, roll[c].pc2 * 100, color=COL[c], linewidth=1.6, label=c)
    ax.set_ylabel("% of variance")
    ax.set_title("PC2 (slope) share of daily curve variance, rolling one-year window")
    ax.legend(loc="upper left", ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_rolling_slope_share.png", dpi=160)
    plt.close(fig)


def section2(C, res):
    start = max(df.index[0] for df in C.values())
    end = min(df.index[-1] for df in C.values())
    # weekly (Wednesday) changes: USD closes after London, so same-day changes are not synchronous
    W = {c: df.loc[start:end].resample("W-WED").last() for c, df in C.items()}
    G = pd.concat({c: w.diff() for c, w in W.items()}, axis=1).dropna()
    w, v = pca(G.values)
    share = w / w.sum()
    # variance of each currency's curve explained by the first k global factors
    Xc = G.values - G.values.mean(axis=0)
    expl = {}
    for k in (1, 2, 3, 4):
        V = v[:, :k]
        fit = Xc @ V @ V.T
        expl[k] = {}
        for c in CCYS:
            cols = [i for i, col in enumerate(G.columns) if col[0] == c]
            expl[k][c] = round(float(1 - ((Xc[:, cols] - fit[:, cols]) ** 2).sum() / (Xc[:, cols] ** 2).sum()) * 100, 1)
    D = pd.concat({c: df.loc[start:end]["10y"].diff() for c, df in C.items()}, axis=1, sort=True).dropna()
    Wk = pd.concat({c: x["10y"].diff() for c, x in W.items()}, axis=1).dropna()
    res["global"] = {
        "start": str(start.date()), "end": str(end.date()), "n_weeks": len(G),
        "share_pct": [round(x * 100, 1) for x in share[:5]],
        "ccy_variance_explained_by_first_k_global_pct": expl,
        "loadings": {f"G{k+1}": {f"{a} {b}": round(float(x), 2) for (a, b), x in zip(G.columns, v[:, k])} for k in range(4)},
        "corr_10y_daily": D.corr().round(2).to_dict(), "corr_10y_weekly": Wk.corr().round(2).to_dict(),
        "usd_today_vs_eur_next_day_corr": round(float(D["USD"].corr(D["EUR"].shift(-1))), 2),
        "usd_today_vs_gbp_next_day_corr": round(float(D["USD"].corr(D["GBP"].shift(-1))), 2),
        "eur_today_vs_usd_next_day_corr": round(float(D["EUR"].corr(D["USD"].shift(-1))), 2),
    }

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.6), sharey=True)
    for k, ax in enumerate(axes):
        for c in CCYS:
            cols = [i for i, col in enumerate(G.columns) if col[0] == c]
            ax.plot(YRS, v[cols, k], color=COL[c], marker="o", markersize=4, label=c)
        ax.axhline(0, color=INK2, linewidth=0.8)
        style_tenor_axis(ax)
        ax.set_title(f"Global factor {k+1} ({share[k]*100:.1f}%)")
        ax.set_xlabel("Tenor (years, log scale)")
    axes[0].set_ylabel("Loading")
    axes[0].legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_global_factors.png", dpi=160)
    plt.close(fig)


def section3(C, res):
    """Weights re-estimated at each month end from the trailing FLY_WIN days, held for the next month."""
    res["hedge"] = {}
    rows = []
    for c, df in C.items():
        lvl = df.diff().mean(axis=1).rename("level")
        slope = (df["30y"] - df["2y"]).diff().rename("slope")
        me = df.index.to_series().groupby(df.index.to_period("M")).last()
        me = me[me >= df.index[FLY_WIN]]
        for fly in FLIES:
            Y = df[list(fly)]
            for how in ("50/50", "PCA changes", "PCA levels"):
                chg = []
                for i, t in enumerate(me[:-1]):
                    wa, wc = fly_weights(Y.loc[:t].iloc[-FLY_WIN:].values, how)
                    nxt = Y.loc[(Y.index > t) & (Y.index <= me.iloc[i + 1])]
                    full = Y.loc[:me.iloc[i + 1]].iloc[-(len(nxt) + 1):]
                    f = full[fly[1]] - wa * full[fly[0]] - wc * full[fly[2]]
                    chg.append(f.diff().dropna())
                s = pd.concat(chg).rename("f").to_frame().join(lvl).join(slope).dropna()
                X = np.column_stack([np.ones(len(s)), s.level, s.slope])
                b, *_ = np.linalg.lstsq(X, s.f, rcond=None)
                r2 = 1 - ((s.f - X @ b) ** 2).sum() / ((s.f - s.f.mean()) ** 2).sum()
                res["hedge"].setdefault(c, {}).setdefault(fly_name(fly), {})[how] = {
                    "oos_days": len(s), "r2_level_slope_pct": round(r2 * 100, 1),
                    "beta_level": round(b[1], 3), "beta_slope": round(b[2], 3), "daily_std_bp": round(s.f.std(), 2)}
                rows.append((c, fly_name(fly), how, r2 * 100))

    df = pd.DataFrame(rows, columns=["ccy", "fly", "how", "r2"])
    fig, ax = plt.subplots(figsize=(9, 3.8))
    labels = [f"{c}\n{f}" for c in CCYS for f in [fly_name(x) for x in FLIES]]
    x = np.arange(len(labels))
    for j, (how, col) in enumerate((("50/50", NEUTRAL), ("PCA changes", "#2a78d6"), ("PCA levels", "#6250d6"))):
        vals = [df[(df.ccy == c) & (df.fly == f) & (df.how == how)].r2.iloc[0]
                for c in CCYS for f in [fly_name(z) for z in FLIES]]
        bars = ax.bar(x + (j - 1) * 0.27, vals, width=0.25, color=col, label=how)
        for b_, v_ in zip(bars, vals):
            ax.text(b_.get_x() + b_.get_width() / 2, v_ + 0.8, f"{v_:.0f}", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, labels, fontsize=9)
    ax.set_ylabel("% of daily fly variance")
    ax.set_title("Fly variance explained by level and slope, out of sample")
    ax.legend(loc="upper right", ncol=3, fontsize=9)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_hedge_test.png", dpi=160)
    plt.close(fig)


def backtest(Y, how, enter, exit_, hold):
    """One position at a time. At each date with no position: weights and percentile from the trailing
    FLY_WIN days (data to that date only). Enter if the fly is at or beyond the enter percentile.
    Weights and the reference distribution stay fixed for the life of the trade. Exit when the fly is back
    inside the exit percentile or after `hold` days. P&L in bp of fly with the body DV01 = 1."""
    vals = Y.values
    idx = Y.index
    daily = np.zeros(len(Y))
    trades = []
    i, pos = FLY_WIN, 0
    while i < len(Y):
        if pos == 0:
            win = vals[i - FLY_WIN + 1:i + 1]
            wa, wc = fly_weights(win, how)
            F = win[:, 1] - wa * win[:, 0] - wc * win[:, 2]
            pct = (F < F[-1]).mean()
            if pct >= enter or pct <= 1 - enter:
                pos = -1 if pct >= enter else 1   # fly high = body cheap: receive body, pay wings
                hi, hist, ww, e_i = pct >= enter, F, (wa, wc), i
            i += 1
            continue
        f = lambda j: vals[j, 1] - ww[0] * vals[j, 0] - ww[1] * vals[j, 2]
        daily[i] = pos * (f(i) - f(i - 1))
        pct = (hist < f(i)).mean()
        if (hi and pct <= exit_) or ((not hi) and pct >= 1 - exit_) or (i - e_i >= hold):
            trades.append({"entry": idx[e_i], "exit": idx[i], "side": "receive body" if pos == -1 else "pay body",
                           "pnl_bp": pos * (f(i) - f(e_i)), "days": i - e_i, "timed_out": i - e_i >= hold,
                           "wa": ww[0], "wc": ww[1]})
            pos = 0
        i += 1
    return pd.DataFrame(trades), pd.Series(daily[FLY_WIN:], index=idx[FLY_WIN:])


def stats(t, d):
    if len(t) == 0:
        return {"trades": 0}
    return {"trades": len(t), "hit_rate_pct": round((t.pnl_bp > 0).mean() * 100), "avg_bp": round(t.pnl_bp.mean(), 2),
            "total_bp": round(t.pnl_bp.sum(), 1), "worst_bp": round(t.pnl_bp.min(), 1), "best_bp": round(t.pnl_bp.max(), 1),
            "avg_days": round(t.days.mean()), "timeouts": int(t.timed_out.sum()),
            "timeout_avg_bp": round(t[t.timed_out].pnl_bp.mean(), 2) if t.timed_out.any() else None,
            "sharpe": round(d.mean() / d.std() * np.sqrt(252), 2) if d.std() > 0 else None}


def section4(C, res):
    res["salomon"] = {"base": {}, "grid": {}}
    all_trades, curves = [], {}
    for c, df in C.items():
        for fly in FLIES:
            Y = df[list(fly)]
            for how in ("PCA levels", "PCA changes", "50/50"):
                t, d = backtest(Y, how, ENTER, EXIT, MAX_HOLD)
                res["salomon"]["base"].setdefault(c, {}).setdefault(fly_name(fly), {})[how] = stats(t, d)
                if len(t):
                    all_trades.append(t.assign(ccy=c, fly=fly_name(fly), weights=how))
                curves[(c, fly_name(fly), how)] = d.cumsum()
            for (en, ex) in GRID:
                for hold in HOLDS:
                    t, d = backtest(Y, "PCA levels", en, ex, hold)
                    s = stats(t, d)
                    res["salomon"]["grid"].setdefault(f"{int(round((1-en)*100))}/{int(round((1-ex)*100))} hold {hold}", {})[f"{c} {fly_name(fly)}"] = s
    T = pd.concat(all_trades)
    T.to_csv(OUT / "salomon_trades.csv", index=False, float_format="%.3f")
    agg = {}
    for how, g in T.groupby("weights"):
        agg[how] = {"trades": len(g), "hit_rate_pct": round((g.pnl_bp > 0).mean() * 100), "avg_bp": round(g.pnl_bp.mean(), 2),
                    "median_bp": round(g.pnl_bp.median(), 2), "worst_bp": round(g.pnl_bp.min(), 1),
                    "timeout_share_pct": round(g.timed_out.mean() * 100),
                    "avg_bp_converged": round(g[~g.timed_out].pnl_bp.mean(), 2),
                    "avg_bp_timed_out": round(g[g.timed_out].pnl_bp.mean(), 2)}
    res["salomon"]["pooled"] = agg
    L = T[T.weights == "PCA levels"]
    by_entry_2022 = L.entry.dt.year == 2022
    res["salomon"]["pca_levels_2022"] = {
        "trades_entered_2022": int(by_entry_2022.sum()),
        "pnl_entered_2022_by_fly": L[by_entry_2022].groupby(["ccy", "fly"]).pnl_bp.sum().round(1)
            .rename(lambda x: x, level=0).to_dict(),
        "pnl_total_by_fly": L.groupby(["ccy", "fly"]).pnl_bp.sum().round(1).to_dict(),
        "avg_bp_ex_2022_entries": round(float(L[~by_entry_2022].pnl_bp.mean()), 2),
        "avg_bp_2022_entries": round(float(L[by_entry_2022].pnl_bp.mean()), 2),
    }
    res["salomon"]["pca_levels_2022"] = {k: ({f"{a} {b}": x for (a, b), x in v.items()} if isinstance(v, dict) else v)
                                         for k, v in res["salomon"]["pca_levels_2022"].items()}
    grid_summary = {}
    for k, v in res["salomon"]["grid"].items():
        sh = [x["sharpe"] for x in v.values() if x.get("sharpe") is not None]
        grid_summary[k] = {"median_sharpe": round(float(np.median(sh)), 2), "positive_of_6": int(sum(s > 0 for s in sh)),
                           "avg_bp_per_trade_pooled": round(float(np.mean([x["avg_bp"] for x in v.values() if x["trades"]])), 2)}
    res["salomon"]["grid_summary"] = grid_summary

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), sharey=True)
    for ax, f in zip(axes, [fly_name(x) for x in FLIES]):
        for c in CCYS:
            s = curves[(c, f, "PCA levels")]
            ax.plot(s.index, s.values, color=COL[c], linewidth=1.6, label=c)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_title(f"{f}: cumulative P&L, PCA-levels flies")
        ax.set_ylabel("bp of fly (body DV01 = 1)")
    axes[1].legend(loc="lower right", ncol=3)
    fig.tight_layout()
    fig.savefig(OUT / "fig5_salomon_backtest.png", dpi=160)
    plt.close(fig)


def section5(C, res):
    """Rolling one-year PCA on levels; residual = actual minus 3-factor reconstruction (CS/StanChart)."""
    res["residuals"] = {}
    last = {}
    for c, df in C.items():
        X, rows = df.values, []
        for i in range(ROLL, len(df)):
            win = X[i - ROLL + 1:i + 1]
            mu = win.mean(axis=0)
            _, v = pca(win)
            V = v[:, :3]
            rows.append((X[i] - mu) - V @ (V.T @ (X[i] - mu)))
        R = pd.DataFrame(rows, index=df.index[ROLL:], columns=TENORS)
        Z = (R - R.rolling(ROLL).mean()) / R.rolling(ROLL).std()
        hl = {}
        for t in TENORS:
            s = R[t].values
            b = np.polyfit(s[:-1], np.diff(s), 1)[0]
            hl[t] = round(float(np.log(2) / -b), 1) if b < 0 else None
        res["residuals"][c] = {"date": str(R.index[-1].date()), "resid_bp": R.iloc[-1].round(1).to_dict(),
                               "z": Z.iloc[-1].round(2).to_dict(), "resid_std_bp": R.std().round(2).to_dict(),
                               "half_life_days": hl, "max_abs_z_now": round(float(Z.iloc[-1].abs().max()), 2),
                               "share_days_any_abs_z_gt_2_pct": round(float((Z.abs() > 2).any(axis=1)[ROLL:].mean() * 100), 1)}
        last[c] = Z.iloc[-1]
    fig, ax = plt.subplots(figsize=(9, 3.6))
    x = np.arange(len(TENORS))
    for j, c in enumerate(CCYS):
        ax.bar(x + (j - 1) * 0.27, last[c].values, width=0.25, color=COL[c],
               label=f"{c} ({res['residuals'][c]['date']})")
    ax.axhline(0, color=INK2, linewidth=0.8)
    for y in (-2, 2):
        ax.axhline(y, color=NEUTRAL, linewidth=0.8, linestyle="--")
    ax.set_xticks(x, TENORS)
    ax.set_ylabel("z-score (positive = cheap)")
    ax.set_title("Residual to 3-factor fair value on the last date in the data")
    ax.legend(loc="upper right", ncol=3, fontsize=9)
    ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig6_residual_zscores.png", dpi=160)
    plt.close(fig)


def main():
    C = load()
    res = {}
    section1(C, res)
    section2(C, res)
    section3(C, res)
    section4(C, res)
    section5(C, res)
    (OUT / "results.json").write_text(json.dumps(res, indent=2, default=str))
    print(json.dumps(res, indent=1, default=str)[:20000])


if __name__ == "__main__":
    main()
