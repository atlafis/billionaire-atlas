"""The questions this project asks, each answered by one function.

Every function takes the processed tables, returns a dict of numbers (which
feed ``reports/findings.md``) and writes at most one figure.
"""

from __future__ import annotations

from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter, PercentFormatter

from . import config, stats, style
from .build import ORIGIN_GROWING, ORIGIN_INHERITED, ORIGIN_SELF, ORIGINS

SOURCE = "Source: Forbes World's Billionaires via PIIE/CORGIS (1996-2014) and komed3/rtb-api (2019-2026)."
ORIGIN_COLORS = dict(zip(ORIGINS, style.SERIES))


@dataclass
class Tables:
    people: pd.DataFrame
    annual: pd.DataFrame
    historical: pd.DataFrame

    @classmethod
    def load(cls) -> Tables:
        return cls(pd.read_csv(config.PEOPLE_CSV), pd.read_csv(config.ANNUAL_CSV),
                   pd.read_csv(config.HISTORICAL_CSV))

    @property
    def current(self) -> pd.DataFrame:
        return self.people[self.people["on_latest_list"]]

    @property
    def entrants(self) -> pd.DataFrame:
        """People whose first appearance is observed exactly (2020 onwards)."""
        return self.people[self.people["first_seen_exact"]]

    @property
    def snapshot(self) -> str:
        return str(self.annual["last_list_date"].max())


# ------------------------------------------------------------------ 1. overview

def overview(t: Tables) -> dict:
    cur = t.current
    origin = cur["wealth_origin"].value_counts(normalize=True)
    hist_self = (t.historical.assign(s=t.historical["inheritance"].eq("not inherited"))
                 .dropna(subset=["inheritance"]).groupby("year")["s"].mean())
    return {
        "snapshot": t.snapshot,
        "people_total": len(t.people),
        "people_current": len(cur),
        "wealth_current_tn": cur["net_worth_latest_bn"].sum() / 1000,
        "countries_current": cur["country"].nunique(),
        "women_share": cur["gender"].eq("female").mean(),
        "self_made_share": origin.get(ORIGIN_SELF, 0),
        "growing_share": origin.get(ORIGIN_GROWING, 0),
        "inherited_share": origin.get(ORIGIN_INHERITED, 0),
        "self_made_share_by_year": {int(y): v for y, v in hist_self.items()},
        "linked_share_2014": t.historical.loc[t.historical["year"] == 2014, "link_method"].notna().mean(),
    }


# ------------------------------------------------------ 2. origin, by country

def origin_by_country(t: Tables, top: int = 12) -> dict:
    cur = t.current.dropna(subset=["wealth_origin"])
    counts = cur["country"].value_counts().head(top)
    share = (pd.crosstab(cur["country"], cur["wealth_origin"], normalize="index")
             .loc[counts.index, list(ORIGINS)].sort_values(ORIGIN_SELF))

    fig, ax = plt.subplots(figsize=(9, 6.2))
    left = np.zeros(len(share))
    for origin in ORIGINS:
        v = share[origin].to_numpy()
        ax.barh(share.index, v, left=left, color=ORIGIN_COLORS[origin], height=0.66,
                edgecolor=style.SURFACE, linewidth=2, label=origin)
        left += v
    for i, (country, row) in enumerate(share.iterrows()):
        ax.text(row[ORIGIN_SELF] - 0.012, i, f"{row[ORIGIN_SELF]:.0%}", ha="right", va="center",
                color="white", fontsize=9, fontweight="bold")
        ax.text(1.01, i, f"n={counts[country]:,}", va="center", fontsize=8.5, color=style.INK_2)
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(PercentFormatter(1))
    ax.grid(axis="y", visible=False)
    ax.set_title("Where fortunes are built rather than inherited")
    style.subtitle(ax, f"Share of each country's billionaires by origin of wealth, {t.snapshot}. "
                       "Top 12 countries by headcount.")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.06))
    style.save(fig, config.FIGURES / "01_origin_by_country.png", note=SOURCE)
    return {"self_made_share_by_country": share[ORIGIN_SELF].round(3).to_dict(),
            "headcount_by_country": counts.to_dict()}


# ------------------------------------------- 3. who becomes a billionaire, when

def entrants_by_year(t: Tables) -> dict:
    e = t.entrants.copy()
    e["group"] = np.where(e["industry"].eq("Technology"), "Technology",
                          np.where(e["industry"].eq("Finance & Investments"),
                                   "Finance & Investments", "Everything else"))
    groups = ["Technology", "Finance & Investments", "Everything else"]
    colors = dict(zip(groups, style.SERIES))
    tab = pd.crosstab(e["first_seen_year"].astype(int), e["group"]).reindex(columns=groups, fill_value=0)

    fig, ax = plt.subplots(figsize=(9, 5.2))
    bottom = np.zeros(len(tab))
    for g in groups:
        ax.bar(tab.index, tab[g], bottom=bottom, color=colors[g], width=0.68,
               edgecolor=style.SURFACE, linewidth=2, label=g)
        bottom += tab[g].to_numpy()
    for x, total in zip(tab.index, bottom):
        ax.text(x, total + 8, f"{int(total)}", ha="center", fontsize=9, color=style.INK)
    last = int(tab.index.max())
    ax.set_xticks(tab.index, [str(y) if y != last else f"{y}\n(to {t.snapshot[5:]})" for y in tab.index])
    ax.grid(axis="x", visible=False)
    ax.set_ylabel("People entering the list")
    ax.set_title("New billionaires per year")
    share = tab["Technology"] / tab.sum(axis=1)
    style.subtitle(ax, "First appearance on Forbes' real-time list, people on no earlier list. "
                       f"Tech's share of newcomers: {share.min():.0%} in {share.idxmin()}, "
                       f"{share.iloc[-1]:.0%} in {share.index[-1]}.")
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.12))
    style.save(fig, config.FIGURES / "02_new_billionaires_by_year.png", note=SOURCE)
    share = (tab["Technology"] / tab.sum(axis=1)).round(3)
    return {"entrants_total": len(e), "entrants_by_year": tab.sum(axis=1).to_dict(),
            "tech_share_by_year": share.to_dict()}


def entry_age(t: Tables, min_n: int = 30) -> dict:
    e = t.entrants.dropna(subset=["age_at_first_seen", "industry"])
    g = (e.groupby("industry")["age_at_first_seen"]
         .agg(median="median", q1=lambda s: s.quantile(.25), q3=lambda s: s.quantile(.75), n="size"))
    g = g[g["n"] >= min_n].sort_values("median", ascending=False)

    fig, ax = plt.subplots(figsize=(9, 6.4))
    y = np.arange(len(g))
    ax.hlines(y, g["q1"], g["q3"], color=style.BLUE, alpha=0.35, linewidth=6)
    ax.scatter(g["median"], y, color=style.BLUE, s=60, zorder=3, edgecolor=style.SURFACE, linewidth=2)
    overall = e["age_at_first_seen"].median()
    ax.axvline(overall, color=style.INK_3, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(overall + 0.4, len(g) - 0.4, f"all industries: {overall:.0f}", color=style.INK_2, fontsize=8.5)
    for yi, (_, row) in zip(y, g.iterrows()):
        ax.text(row["q3"] + 0.8, yi, f"{row['median']:.0f}  (n={int(row['n'])})", va="center",
                fontsize=8.5, color=style.INK_2)
    ax.set_yticks(y, g.index)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Age when first on the list (dot = median, bar = middle 50%)")
    ax.set_title("Tech and media billionaires arrive about ten years younger")
    style.subtitle(ax, f"Age at first appearance, {len(e):,} people who entered the list 2020-2026.")
    style.save(fig, config.FIGURES / "03_entry_age_by_industry.png", note=SOURCE)

    youngest = (e[e["wealth_origin"].eq(ORIGIN_SELF)].nsmallest(5, "age_at_first_seen")
                [["name", "age_at_first_seen", "first_seen_year", "source_of_wealth"]])
    by_origin = e.groupby("wealth_origin")["age_at_first_seen"].median()
    return {"entry_age_median": overall, "entry_age_by_industry": g["median"].to_dict(),
            "entry_age_by_origin": by_origin.to_dict(),
            "youngest_self_made": youngest.to_dict("records"),
            "under_40_share": float((e["age_at_first_seen"] < 40).mean())}


# -------------------------------------------------------- 4. how unequal is it

def wealth_tail(t: Tables) -> dict:
    w = t.current["net_worth_latest_bn"].dropna().to_numpy()
    w = w[w >= 1]  # a handful of list entries sit just under $1B
    fit = stats.fit_pareto(w, bootstrap=200, seed=7)
    x, p = stats.ccdf(w)

    fig, ax = plt.subplots(figsize=(9, 5.6))
    ax.scatter(x, p, s=10, color=style.BLUE, alpha=0.55, linewidth=0, label="Billionaires (one dot each)")
    xs = np.geomspace(fit.xmin, x.max(), 50)
    p_at_xmin = (w >= fit.xmin).mean()
    ax.plot(xs, p_at_xmin * (xs / fit.xmin) ** (-fit.tail_index), color=style.ORANGE,
            label=f"Pareto fit, tail index {fit.tail_index:.2f}")
    ax.axvline(fit.xmin, color=style.INK_3, linewidth=1, linestyle=(0, (4, 3)))
    ax.text(fit.xmin * 1.06, 0.5, f"power law holds above ${fit.xmin:.1f}B", fontsize=8.5,
            color=style.INK_2)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}B"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v * 100:g}%"))
    ax.set_xlabel("Net worth (log scale)")
    ax.set_ylabel("Share of billionaires at least this rich")
    for name in ("Elon Musk", "Jeff Bezos", "Warren Buffett"):
        row = t.current[t.current["name"] == name]
        if len(row):
            v = row["net_worth_latest_bn"].iloc[0]
            ax.annotate(name, (v, (w >= v).mean()), xytext=(-28, -16), textcoords="offset points",
                        ha="right", va="center", fontsize=8.5, color=style.INK_2,
                        arrowprops={"arrowstyle": "-", "color": style.INK_3, "lw": 0.8, "shrinkB": 4})
    ax.set_title("A straight line on a log-log plot: Pareto's law")
    style.subtitle(ax, f"Distribution of {len(w):,} fortunes on {t.snapshot}. "
                       f"Each doubling of wealth makes a fortune {2 ** fit.tail_index:.1f} times rarer.")
    ax.legend(loc="lower left")
    style.save(fig, config.FIGURES / "04_pareto_tail.png", note=SOURCE)

    return {"pareto_alpha": fit.alpha, "pareto_tail_index": fit.tail_index,
            "pareto_ci": (fit.ci_low - 1, fit.ci_high - 1), "pareto_xmin": fit.xmin,
            "pareto_n_tail": fit.n_tail, "pareto_ks": fit.ks,
            "gini_within_list": stats.gini(w), "top10_share": stats.top_share(w, 10),
            "top1pct_share": stats.top_share(w, max(1, len(w) // 100))}


def concentration_over_time(t: Tables, n: int = 400) -> dict:
    """Share of the top-``n`` fortunes held by the ten richest, 1996 to today.

    The list itself grew from 423 to over 3,000 people, and a top-10 share of
    a longer list shrinks for that reason alone. Holding the comparison group
    fixed at the 400 richest (the 1996 list size) removes that artefact.
    """
    rows = []
    for y, g in t.historical.groupby("year"):
        w = np.sort(g["net_worth_bn"].dropna().to_numpy())[::-1][:n]
        rows.append((int(y), stats.top_share(w, 10), w[-1]))
    for y, g in t.annual.groupby("year"):
        w = np.sort(g["net_worth_year_end_bn"].dropna().to_numpy())[::-1][:n]
        rows.append((int(y), stats.top_share(w, 10), w[-1]))
    df = pd.DataFrame(rows, columns=["year", "top10", "cutoff"]).sort_values("year")

    fig, ax = plt.subplots(figsize=(9, 5))
    style.plot_gapped(ax, df["year"], df["top10"], style.BLUE)
    for _, r in df[df["year"].isin([1996, 2001, 2014, 2019, df["year"].max()])].iterrows():
        ax.annotate(f"{r['top10']:.0%}", (r["year"], r["top10"]), xytext=(0, 10),
                    textcoords="offset points", ha="center", fontsize=9)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylim(0, df["top10"].max() * 1.25)
    ax.set_ylabel(f"Top 10 as a share of the top {n}")
    ax.grid(axis="x", visible=False)
    ax.set_title("The ten richest hold a record share of the elite")
    style.subtitle(ax, f"Wealth of the 10 richest divided by wealth of the {n} richest. "
                       "Dashed segments cross years with no data.")
    style.save(fig, config.FIGURES / "05_top10_share.png", note=SOURCE)
    return {"top10_of_top400_by_year": dict(zip(df["year"], df["top10"].round(3))),
            "rank400_cutoff_bn_by_year": dict(zip(df["year"], df["cutoff"].round(2)))}


# ---------------------------------------------- 5. do the rich get richer faster

EXIT_CEILING = 3.0  # $B


def year_pairs(t: Tables, last_full_year: int = 2025, exit_value: float | None = None) -> pd.DataFrame:
    """Year-end wealth in year y and y+1 for everyone on the list in year y.

    People missing from every list in y+1 fell below $1B (or died). With
    ``exit_value=None`` they are dropped, which keeps only survivors. With a
    number, their next-year wealth is set to it: $1B is an upper bound for
    someone who is no longer listed, so it understates how far they fell.
    """
    a = t.annual[["person_id", "year", "net_worth_year_end_bn"]]
    nxt = a.assign(year=a["year"] - 1).rename(columns={"net_worth_year_end_bn": "next_w"})
    d = a[a["year"] < last_full_year].merge(nxt, on=["person_id", "year"], how="left")
    d["exited"] = d["next_w"].isna()
    if exit_value is None:
        d = d[~d["exited"]]
    else:
        # A $20B fortune does not fall below $1B in a year; when someone that
        # rich vanishes it is a death, a family split or a re-filed profile.
        # Only exits from below EXIT_CEILING are treated as falling off.
        d = d[~(d["exited"] & (d["net_worth_year_end_bn"] >= EXIT_CEILING))]
        d["next_w"] = d["next_w"].fillna(exit_value)
    d = d[(d["net_worth_year_end_bn"] > 0) & (d["next_w"] > 0)]
    d["x"] = np.log10(d["net_worth_year_end_bn"])
    d["g"] = np.log(d["next_w"] / d["net_worth_year_end_bn"])
    return d


def _year_adjusted(d: pd.DataFrame) -> np.ndarray:
    return (d["g"] - d.groupby("year")["g"].transform("mean") + d["g"].mean()).to_numpy()


def growth_vs_size(t: Tables) -> dict:
    """Gibrat's law: is a fortune's growth rate independent of its size?

    The naive answer is biased by survivorship: a small fortune that shrinks
    falls off the list and is never seen again, so the survivors among small
    fortunes look like fast growers. The test is run twice, once on survivors
    and once with every exit put back in at $1B.
    """
    surv = year_pairs(t)
    full = year_pairs(t, exit_value=1.0)
    reg_s = stats.demeaned_ols(surv["x"], surv["g"], surv["year"])
    reg_f = stats.demeaned_ols(full["x"], full["g"], full["year"])
    reg_half = stats.demeaned_ols(*(lambda d: (d["x"], d["g"], d["year"]))(year_pairs(t, exit_value=0.5)))

    fig, ax = plt.subplots(figsize=(9, 5.4))
    ax.axhline(0, color=style.INK_3, linewidth=1)
    for d, color, label, shift in ((surv, style.ORANGE, "Survivors only (the naive view)", 0.985),
                                   (full, style.BLUE, "Including people who fell off the list", 1.015)):
        mx, my, half = stats.binned_means(d["x"].to_numpy(), _year_adjusted(d), bins=10)
        mid, lo, hi = np.expm1(my), np.expm1(my - half), np.expm1(my + half)
        ax.errorbar(10 ** mx * shift, mid, yerr=[mid - lo, hi - mid], fmt="o-", color=color, ecolor=color,
                    elinewidth=2, linewidth=1.2, capsize=0, markersize=7, markeredgecolor=style.SURFACE,
                    markeredgewidth=2, label=label)
    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"${v:,.0f}B" if v >= 1 else f"${v:.1f}B"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0%}"))
    ax.set_xlabel("Net worth at the end of the year (decile bins, log scale)")
    ax.set_ylabel("Average change over the next year")
    ax.grid(axis="x", visible=False)
    ax.set_title("Do small fortunes grow faster? Partly a survivorship illusion")
    style.subtitle(ax, f"Year-on-year change 2019-2025, year effects removed, bars = 95% CI. Slope per 10x "
                       f"wealth: {reg_s.slope:+.3f} naive, {reg_f.slope:+.3f} with exits at $1B, "
                       f"{reg_half.slope:+.3f} at $0.5B.")
    ax.legend(loc="lower right")
    style.save(fig, config.FIGURES / "06_growth_vs_size.png",
               note=SOURCE + " People who drop off from under $3B are counted at $1B, an upper bound.")

    ind = t.people.set_index("person_id")["industry"]
    vol = (surv.assign(industry=surv["person_id"].map(ind)).dropna(subset=["industry"])
           .groupby("industry")["g"].agg(["std", "median", "size"]))
    vol = vol[vol["size"] >= 100].sort_values("std", ascending=False)
    exit_rate = full.groupby(pd.cut(full["net_worth_year_end_bn"], [0, 2, 5, 20, np.inf],
                                    labels=["under $2B", "$2-5B", "$5-20B", "over $20B"]),
                             observed=True)["exited"].mean()
    return {"gibrat_survivors": reg_s.__dict__ | {"t": reg_s.t},
            "gibrat_with_exits_at_1B": reg_f.__dict__ | {"t": reg_f.t},
            "gibrat_with_exits_at_0_5B": reg_half.__dict__ | {"t": reg_half.t},
            "exit_rate_by_wealth": {str(k): round(v, 3) for k, v in exit_rate.items()},
            "exit_rate_overall": float(full["exited"].mean()),
            "median_annual_change": float(np.expm1(np.median(surv["g"]))),
            "volatility_by_industry": vol["std"].round(3).to_dict(),
            "median_change_by_industry": np.expm1(vol["median"]).round(3).to_dict()}


# ------------------------------------------------ 6. how long do fortunes last

def survival(t: Tables) -> dict:
    """Of each historical list, what share is still on the list later?"""
    on: dict[int, set[str]] = {int(y): set(g["person_id"]) for y, g in t.historical.groupby("year")}
    on.update({int(y): set(g["person_id"]) for y, g in t.annual.groupby("year")})
    years = sorted(on)

    fig, ax = plt.subplots(figsize=(9, 5.2))
    out = {}
    for cohort, color in zip(config.HISTORICAL_YEARS, style.SERIES):
        members = on[cohort]
        ys = [y for y in years if y >= cohort]
        share = [len(members & on[y]) / len(members) for y in ys]
        out[cohort] = dict(zip(ys, np.round(share, 3)))
        style.plot_gapped(ax, ys, share, color, label=f"{cohort} list (n={len(members):,})", s=30)
        ax.annotate(f"{share[-1]:.0%}", (ys[-1], share[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=9, color=style.INK)
    ax.yaxis.set_major_formatter(PercentFormatter(1, decimals=0))
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Still a billionaire")
    ax.grid(axis="x", visible=False)
    ax.set_title("Most billionaires of the 1990s are no longer on the list")
    style.subtitle(ax, "Share of each historical list found on later lists; dashed segments cross years "
                       "with no data. Exits include deaths.")
    ax.legend(loc="lower left")
    style.save(fig, config.FIGURES / "07_survival.png", note=SOURCE + " People are linked across sources by name.")

    h96 = t.historical[t.historical["year"] == 1996].drop_duplicates("person_id")
    last = years[-1]
    h96 = h96.assign(stayed=h96["person_id"].isin(on[last]),
                     origin=h96["inheritance"].map(lambda s: "self-made" if s == "not inherited" else "inherited"))
    return {"survival": out, "survival_1996_by_origin": h96.groupby("origin")["stayed"].mean().round(3).to_dict()}


# ------------------------------------------------------------------- 7. school

def education(t: Tables) -> dict:
    cur = t.current
    known = cur[cur["education_level"] != "unknown"]
    self_made = known[known["wealth_origin"] == ORIGIN_SELF]
    schools = cur["schools"].dropna().str.split("; ").explode().str.strip()
    schools = schools[~schools.str.contains("high school", case=False)]
    schools = (schools.str.replace(r"^University of Pennsylvania.*", "University of Pennsylvania", regex=True)
               .replace({"Harvard Business School": "Harvard University",
                         "Stanford Graduate School of Business": "Stanford University"})
               .value_counts().head(10))
    return {"education_known_share": len(known) / len(cur),
            "education_levels": known["education_level"].value_counts(normalize=True).round(3).to_dict(),
            "dropout_share_self_made": float(self_made["dropout"].mean()),
            "top_schools": schools.to_dict()}


ALL = (overview, origin_by_country, entrants_by_year, entry_age, wealth_tail,
       concentration_over_time, growth_vs_size, survival, education)


def run_all(t: Tables | None = None) -> dict:
    style.apply()
    t = t or Tables.load()
    results: dict = {}
    for f in ALL:
        results[f.__name__] = f(t)
        print(f"  {f.__name__}")
    return results
