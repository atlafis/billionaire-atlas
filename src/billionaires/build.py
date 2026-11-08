"""Turn the raw sources into three tidy tables.

* ``billionaires.csv`` - one row per person, both sources merged.
* ``net_worth_annual.csv`` - one row per person per year, 2019 onwards.
* ``historical_lists.csv`` - the 1996/2001/2014 list entries, linked to people.

The central derived field is ``first_seen_year``: the earliest year a person
appears on any list we hold. It is an upper bound on the year they became a
billionaire, exact only when the person enters inside a continuous stretch of
data (2020 onwards). ``first_seen_exact`` marks those rows.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pycountry

from . import config
from .names import full_key, link, slug

ORIGIN_SELF = "self-made"
ORIGIN_GROWING = "inherited, growing"
ORIGIN_INHERITED = "inherited"
ORIGINS = (ORIGIN_SELF, ORIGIN_GROWING, ORIGIN_INHERITED)

INDUSTRY_LABELS = {
    "technology": "Technology",
    "manufacturing": "Manufacturing",
    "finance-investments": "Finance & Investments",
    "fashion-retail": "Fashion & Retail",
    "healthcare": "Healthcare",
    "food-beverage": "Food & Beverage",
    "real-estate": "Real Estate",
    "diversified": "Diversified",
    "media-entertainment": "Media & Entertainment",
    "energy": "Energy",
    "metals-mining": "Metals & Mining",
    "automotive": "Automotive",
    "service": "Service",
    "construction-engineering": "Construction & Engineering",
    "logistics": "Logistics",
    "sports": "Sports",
    "telecom": "Telecom",
    "gambling-casinos": "Gambling & Casinos",
}

# PIIE industry codes -> the Forbes industry taxonomy used above.
PIIE_INDUSTRY = {
    "Technology-Computer": "Technology", "Technology-Medical": "Healthcare",
    "Media": "Media & Entertainment", "Retail, Restaurant": "Fashion & Retail",
    "Consumer": "Food & Beverage", "Real Estate": "Real Estate",
    "Money Management": "Finance & Investments", "Hedge funds": "Finance & Investments",
    "Private equity/leveraged buyout": "Finance & Investments",
    "Venture Capital": "Finance & Investments", "Banking": "Finance & Investments",
    "Energy": "Energy", "Mining and metals": "Metals & Mining",
    "Non-consumer industrial": "Manufacturing", "Constrution": "Construction & Engineering",
    "Construction": "Construction & Engineering", "Diversified financial": "Finance & Investments",
    "Other": "Diversified", "Aerospace": "Manufacturing", "Defense": "Manufacturing",
    "Shipping": "Logistics", "Services": "Service",
}


# --------------------------------------------------------------------------- load

def load_rtb_profiles(path: Path = config.RTB_RAW) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_rtb_lists(path: Path = config.RTB_LISTS_RAW) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"citizenship": str, "industry": str, "source": str})
    df["net_worth_bn"] = df.pop("net_worth_m") / 1000
    return df


def load_corgis(path: Path = config.CORGIS_RAW) -> pd.DataFrame:
    df = pd.json_normalize(json.loads(Path(path).read_text()))
    df = df.rename(columns={
        "demographics.age": "age", "demographics.gender": "gender",
        "location.citizenship": "country", "wealth.worth in billions": "net_worth_bn",
        "wealth.type": "route", "wealth.how.inherited": "inheritance",
        "wealth.how.industry": "piie_industry", "company.name": "company",
        "company.founded": "company_founded", "company.relationship": "relationship",
    })
    df["age"] = df["age"].where(df["age"] > 0)  # the source codes unknown age as 0 or negative
    df["company_founded"] = df["company_founded"].where(df["company_founded"] > 1000)
    df["route"] = df["route"].replace("", np.nan)
    df["name"] = df["name"].str.strip()
    return df


# ------------------------------------------------------------------- per-field rules

COUNTRY_OVERRIDES = {"RU": "Russia", "KR": "South Korea", "IR": "Iran", "TW": "Taiwan",
                     "VN": "Vietnam", "VE": "Venezuela", "TZ": "Tanzania", "CZ": "Czechia",
                     "MO": "Macao", "SY": "Syria", "MD": "Moldova"}


def country_name(code: str | None) -> str | None:
    if not isinstance(code, str) or not code:
        return None
    if code.upper() in COUNTRY_OVERRIDES:
        return COUNTRY_OVERRIDES[code.upper()]
    c = pycountry.countries.get(alpha_2=code.upper())
    if c is None:
        return code.upper()
    return getattr(c, "common_name", None) or c.name


def degree_level(education: list[dict] | None) -> str:
    """Highest stated degree, collapsed to a handful of levels."""
    if not education:
        return "unknown"
    text = " | ".join(str(e.get("degree") or "") for e in education).lower()
    if not text.strip(" |"):
        return "unknown"
    if re.search(r"doctor|ph\.?d|jurisprudence|medical|\bmd\b|\bjd\b", text):
        return "doctorate"
    if re.search(r"master|mba|emba|\bms\b|\bma\b|llm", text):
        return "master"
    if re.search(r"bachelor|\bba\b|\bbs\b|\bbsc\b|llb|bcom|b\.a|b\.s|law degree", text):
        return "bachelor"
    if "drop" in text:
        return "dropout"
    if re.search(r"diploma|high school|associate", text):
        return "diploma or below"
    return "other"


def is_dropout(education: list[dict] | None) -> bool:
    return any("drop" in str(e.get("degree") or "").lower() for e in education or [])


def origin_from_forbes(self_made: dict | None) -> str | None:
    t = (self_made or {}).get("type")
    return {"self-made": ORIGIN_SELF, "inherited and growing": ORIGIN_GROWING,
            "inherited": ORIGIN_INHERITED}.get(t)


def origin_from_piie(inheritance: str | None) -> str | None:
    if not isinstance(inheritance, str):
        return None
    return ORIGIN_SELF if inheritance == "not inherited" else ORIGIN_INHERITED


# ---------------------------------------------------------------------- build tables

def canonical_ids(profiles: list[dict], lists: pd.DataFrame) -> dict[str, str]:
    """Merge Forbes profiles that are the same person under two URIs.

    Forbes sometimes re-files a person under a new URI (most often when the
    order of a Chinese name flips: ``liu-yonghao`` / ``yonghao-liu``). Two URIs
    are merged when their names normalise to the same key, their birth years
    agree, and they never appear on the same daily list. The URI seen most
    recently is kept.
    """
    seen = lists.groupby("uri")["date"].agg(["max", "count"])
    dates = lists.groupby("uri")["date"].apply(set)

    groups: dict[tuple, list[str]] = {}
    for r in profiles:
        info = r.get("info") or {}
        birth = (info.get("birthDate") or "")[:4]
        if info.get("name") and birth:
            groups.setdefault((full_key(info["name"]), birth), []).append(r["uri"])
    # URIs that only appear on lists (no profile) join a group by name alone.
    by_name: dict[str, list[tuple]] = {}
    for key in groups:
        by_name.setdefault(key[0], []).append(key)
    profile_uris = {r["uri"] for r in profiles}
    for uri, name in lists.drop_duplicates("uri")[["uri", "name"]].itertuples(index=False):
        if uri not in profile_uris and len(by_name.get(full_key(name), [])) == 1:
            groups[by_name[full_key(name)][0]].append(uri)

    mapping: dict[str, str] = {}
    for uris in groups.values():
        if len(uris) < 2:
            continue
        overlap = any(dates.get(u, set()) & dates.get(v, set())
                      for i, u in enumerate(uris) for v in uris[i + 1:])
        if overlap:
            continue  # namesakes listed side by side are two people
        keep = max(uris, key=lambda u: (seen["max"].get(u, ""), seen["count"].get(u, 0), u))
        for u in uris:
            if u != keep:
                mapping[u] = keep
    return mapping


def build_rtb(profiles: list[dict], lists: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """One row per person and one per person-year from the real-time archive."""
    alias = canonical_ids(profiles, lists)
    lists = lists.assign(uri=lists["uri"].replace(alias))
    lists = (lists.sort_values("net_worth_bn", ascending=False)
             .drop_duplicates(["date", "uri"]).sort_values(["uri", "date"]))
    last_list = lists["date"].max()

    span = lists.groupby("uri").agg(
        rtb_first_seen=("date", "min"), rtb_last_seen=("date", "max"),
        months_listed=("date", "size"), net_worth_peak_bn=("net_worth_bn", "max"))
    last_row = lists.groupby("uri").tail(1).set_index("uri")
    span["net_worth_latest_bn"] = last_row["net_worth_bn"]
    span["rank_latest"] = last_row["rank"]

    lists = lists.assign(year=lists["date"].str[:4].astype(int))
    annual = (lists.groupby(["uri", "year"])
              .agg(net_worth_year_end_bn=("net_worth_bn", "last"), rank_year_end=("rank", "last"),
                   net_worth_year_max_bn=("net_worth_bn", "max"), months_listed=("date", "size"),
                   last_list_date=("date", "last"))
              .reset_index().rename(columns={"uri": "person_id"}))

    rows = []
    for r in profiles:
        if r["uri"] in alias:
            continue
        info = r.get("info") or {}
        org = info.get("organization") or {}
        edu = info.get("education") or []
        birth = info.get("birthDate")
        rows.append({
            "person_id": r["uri"], "name": info.get("name"),
            "gender": {"m": "male", "f": "female"}.get(info.get("gender")),
            "birth_year": int(birth[:4]) if birth else None,
            "country_code": (info.get("citizenship") or "").upper() or None,
            "industry": INDUSTRY_LABELS.get((info.get("industry") or [None])[0]),
            "source_of_wealth": "; ".join(info.get("source") or []) or None,
            "organization": org.get("name"), "title": org.get("title"),
            "wealth_origin": origin_from_forbes(info.get("selfMade")),
            "self_made_score": (info.get("selfMade") or {}).get("rank"),
            "education_level": degree_level(edu), "dropout": is_dropout(edu),
            "schools": "; ".join(e["school"] for e in edu if e.get("school")) or None,
            "deceased": info.get("deceased"),
        })
    people = pd.DataFrame(rows).set_index("person_id")

    # People who appear on lists but have no profile file: take what the list row says.
    missing = span.index.difference(people.index)
    if len(missing):
        lr = last_row.loc[missing]
        people = pd.concat([people, pd.DataFrame({
            "name": lr["name"], "gender": lr["gender"].map({"m": "male", "f": "female"}),
            "birth_year": lr["date"].str[:4].astype(int) - lr["age"],
            "country_code": lr["citizenship"].str.upper(),
            "industry": lr["industry"].str.split(";").str[0].map(INDUSTRY_LABELS),
            "source_of_wealth": lr["source"].str.replace(";", "; "),
            "education_level": "unknown", "dropout": False,
        }, index=missing)])

    people = people.join(span, how="left")
    people["country"] = people["country_code"].map(country_name)
    people["on_latest_list"] = people["rtb_last_seen"].eq(last_list)
    people.index.name = "person_id"
    return people.reset_index(), annual


def build(corgis: pd.DataFrame, profiles: list[dict], lists: pd.DataFrame) -> dict[str, pd.DataFrame]:
    people, annual = build_rtb(profiles, lists)

    # ---- link historical entries to real-time profiles by name
    links = link(corgis["name"].unique(), zip(people["person_id"], people["name"]))
    corgis = corgis.copy()
    corgis["person_id"] = corgis["name"].map(lambda n: links.get(n, (None,))[0])
    corgis["link_method"] = corgis["name"].map(lambda n: links.get(n, (None, None))[1])
    unlinked = corgis["person_id"].isna()
    corgis.loc[unlinked, "person_id"] = "piie-" + corgis.loc[unlinked, "name"].map(slug)
    corgis["birth_est"] = corgis["year"] - corgis["age"]

    # ---- summarise each person's historical record
    hist = (corgis.sort_values("year")
            .groupby("person_id")
            .agg(hist_name=("name", "first"), hist_first_year=("year", "min"),
                 hist_years=("year", lambda s: ",".join(map(str, sorted(set(s))))),
                 hist_gender=("gender", "first"), hist_country=("country", "first"),
                 hist_route=("route", "first"), hist_inheritance=("inheritance", "first"),
                 hist_industry=("piie_industry", "first"), hist_company=("company", "first"),
                 company_founded=("company_founded", "min"),
                 hist_birth_year=("birth_est", "median"), link_method=("link_method", "first")))
    hist["hist_birth_year"] = hist["hist_birth_year"].round()
    hist = hist.reset_index()

    df = people.merge(hist, on="person_id", how="outer")

    # ---- harmonise the fields both sources carry; the newer source wins
    df["name"] = df["name"].fillna(df["hist_name"])
    df["gender"] = df["gender"].fillna(df["hist_gender"])
    df["country"] = df["country"].fillna(df["hist_country"])
    df["birth_year"] = df["birth_year"].fillna(df["hist_birth_year"])
    df["industry"] = df["industry"].fillna(df["hist_industry"].map(PIIE_INDUSTRY))
    df["source_of_wealth"] = df["source_of_wealth"].fillna(df["hist_company"])
    df["wealth_origin"] = df["wealth_origin"].fillna(df["hist_inheritance"].map(origin_from_piie))
    df["education_level"] = df["education_level"].fillna("unknown")
    df["dropout"] = df["dropout"].fillna(False).astype(bool)

    # ---- when did they first show up?
    rtb_first_year = pd.to_numeric(df["rtb_first_seen"].str[:4])
    df["first_seen_year"] = pd.concat([df["hist_first_year"], rtb_first_year], axis=1).min(axis=1)
    # Exact only if the person entered inside the continuous monthly record and
    # was not already on a historical list.
    df["first_seen_exact"] = df["rtb_first_seen"].gt(config.RTB_FIRST_DATE) & df["hist_first_year"].isna()
    df["age_at_first_seen"] = df["first_seen_year"] - df["birth_year"]
    df.loc[(df["age_at_first_seen"] < 0) | (df["age_at_first_seen"] > 110), "age_at_first_seen"] = np.nan
    df["years_from_founding"] = df["first_seen_year"] - df["company_founded"]
    df.loc[df["years_from_founding"] < 0, "years_from_founding"] = np.nan

    df["on_latest_list"] = df["on_latest_list"].fillna(False).astype(bool)
    df["linked_across_sources"] = df["link_method"].notna()

    cols = [
        "person_id", "name", "gender", "birth_year", "country", "country_code", "industry",
        "source_of_wealth", "organization", "title", "wealth_origin", "self_made_score",
        "hist_route", "hist_inheritance", "education_level", "dropout", "schools",
        "first_seen_year", "first_seen_exact", "age_at_first_seen", "company_founded",
        "years_from_founding", "hist_years", "rtb_first_seen", "rtb_last_seen",
        "months_listed", "on_latest_list", "deceased", "net_worth_latest_bn", "rank_latest",
        "net_worth_peak_bn", "linked_across_sources", "link_method",
    ]
    df = df[cols].rename(columns={"hist_route": "piie_route", "hist_inheritance": "piie_inheritance",
                                  "hist_years": "historical_lists"})
    for c in ("birth_year", "first_seen_year", "age_at_first_seen", "company_founded",
              "years_from_founding", "months_listed", "rank_latest", "self_made_score"):
        df[c] = df[c].astype("Int64")
    df = df.sort_values(["net_worth_latest_bn", "name"], ascending=[False, True], na_position="last")

    historical = corgis[["person_id", "name", "year", "rank", "net_worth_bn", "age", "gender",
                         "country", "route", "inheritance", "piie_industry", "company",
                         "company_founded", "relationship", "link_method"]]
    return {"people": df.reset_index(drop=True),
            "annual": annual.sort_values(["person_id", "year"]).reset_index(drop=True),
            "historical": historical.sort_values(["year", "rank"]).reset_index(drop=True)}


def build_all() -> dict[str, pd.DataFrame]:
    tables = build(load_corgis(), load_rtb_profiles(), load_rtb_lists())
    config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    for name, path in (("people", config.PEOPLE_CSV), ("annual", config.ANNUAL_CSV),
                       ("historical", config.HISTORICAL_CSV)):
        df = tables[name]
        floats = df.select_dtypes("float").columns
        df.assign(**{c: df[c].round(4) for c in floats}).to_csv(path, index=False)
    p = tables["people"]
    print(f"{len(p):,} people  |  {p['on_latest_list'].sum():,} on the latest list  |  "
          f"{p['linked_across_sources'].sum():,} linked across sources")
    return tables
