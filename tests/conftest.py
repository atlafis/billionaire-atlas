"""A miniature, hand-written version of both raw sources.

It is small enough to reason about by eye, and covers the awkward cases:
a person filed under two URIs, a namesake pair, a person who only appears on
the historical lists, and a missing age coded as 0.
"""

import pandas as pd
import pytest


def _profile(uri, name, birth, origin="self-made", industry="technology", country="us", edu=None):
    return {"uri": uri, "info": {
        "name": name, "birthDate": birth, "gender": "m", "citizenship": country,
        "industry": [industry], "source": ["Acme"], "deceased": False,
        "education": edu or [], "organization": {"name": "Acme", "title": "CEO"},
        "selfMade": {"type": origin, "rank": 8},
    }, "latest": None}


@pytest.fixture
def profiles():
    return [
        _profile("ada-lovelace", "Ada Lovelace", "1975-01-01", edu=[{"school": "MIT", "degree": "Drop Out"}]),
        _profile("yonghao-liu", "Yonghao Liu", "1951-01-01", origin="inherited"),
        _profile("liu-yonghao", "Liu Yonghao", "1951-01-01", origin="inherited"),
        _profile("wang-wei", "Wang Wei", "1970-01-01", industry="manufacturing", country="cn"),
        _profile("wei-wang", "Wei Wang", "1970-01-01", industry="manufacturing", country="cn"),
        _profile("old-timer", "Old Timer", "1930-01-01", origin="inherited", industry="real-estate"),
    ]


@pytest.fixture
def lists():
    rows = []
    for date in ["2019-11-07", "2020-12-31", "2021-12-31"]:
        rows += [(date, "old-timer", "Old Timer", 1, 50_000.0)]
        rows += [(date, "wang-wei", "Wang Wei", 3, 2_000.0), (date, "wei-wang", "Wei Wang", 4, 1_500.0)]
    rows += [("2019-11-07", "yonghao-liu", "Yonghao Liu", 2, 3_000.0),
             ("2020-12-31", "liu-yonghao", "Liu Yonghao", 2, 3_300.0),
             ("2021-12-31", "liu-yonghao", "Liu Yonghao", 2, 3_600.0),
             ("2021-12-31", "ada-lovelace", "Ada Lovelace", 5, 1_200.0)]
    df = pd.DataFrame(rows, columns=["date", "uri", "name", "rank", "net_worth_m"])
    df["net_worth_bn"] = df.pop("net_worth_m") / 1000
    for c in ["gender", "age", "citizenship", "industry", "source"]:
        df[c] = None
    return df


@pytest.fixture
def corgis():
    return pd.DataFrame([
        {"name": "Old Timer", "year": 1996, "rank": 1, "net_worth_bn": 5.0, "age": 66, "gender": "male",
         "country": "United States", "route": "inherited", "inheritance": "father",
         "piie_industry": "Real Estate", "company": "Timer Co", "company_founded": 1950.0,
         "relationship": "owner"},
        {"name": "Gone Forever", "year": 2001, "rank": 2, "net_worth_bn": 2.0, "age": None,
         "gender": "male", "country": "France", "route": "founder non-finance",
         "inheritance": "not inherited", "piie_industry": "Technology-Computer", "company": "Gone SA",
         "company_founded": 1990.0, "relationship": "founder"},
    ])
