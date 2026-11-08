"""Paths and pinned data sources.

Every source is pinned to a commit so that `make all` reproduces the exact
snapshot the committed results were built from. Pass ``--latest`` to the
``fetch`` command to pull the newest data instead.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "reports" / "figures"
REPORT = ROOT / "reports" / "findings.md"

# Forbes World's Billionaires 1996, 2001, 2014, annotated by the Peterson
# Institute for International Economics (Freund & Oliver, 2016), as packaged
# by the CORGIS Dataset Project.
CORGIS_REPO = "corgis-edu/corgis"
CORGIS_COMMIT = "ff4cc903f66e683b8e464247e4437a70742a4de8"
CORGIS_PATH = "website/datasets/json/billionaires/billionaires.json"

# Forbes Real-Time Billionaires archive (2019 onwards), MIT-licensed mirror.
RTB_REPO = "komed3/rtb-api"
RTB_COMMIT = "2a293c0b7059cb4daca44fe6031fb00b58580c74"
# Only structured fields are fetched. Forbes' biography prose is deliberately
# left out: it is not needed for the analysis and is not ours to redistribute.
RTB_FILES = ("info", "latest")

CORGIS_RAW = DATA_RAW / "corgis_billionaires.json"
RTB_RAW = DATA_RAW / "rtb_profiles.jsonl.gz"
RTB_LISTS_RAW = DATA_RAW / "rtb_monthly_lists.csv.gz"

PEOPLE_CSV = DATA_PROCESSED / "billionaires.csv"
ANNUAL_CSV = DATA_PROCESSED / "net_worth_annual.csv"
HISTORICAL_CSV = DATA_PROCESSED / "historical_lists.csv"
SOURCES_JSON = DATA_PROCESSED / "SOURCES.json"

HISTORICAL_YEARS = (1996, 2001, 2014)
RTB_FIRST_DATE = "2019-11-07"  # first daily list in the archive; anyone on it is left-censored
