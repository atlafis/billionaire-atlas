"""Download the raw data.

Both sources live on GitHub. The real-time archive is ~2 GB of small files, so
it is fetched with a sparse, blob-less git checkout (two structured files per
profile plus one daily list per month) and compacted into two gzipped files.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import config


def _run(cmd: list[str], cwd: Path) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def fetch_corgis(dest: Path = config.CORGIS_RAW, ref: str = config.CORGIS_COMMIT) -> str:
    url = f"https://raw.githubusercontent.com/{config.CORGIS_REPO}/{ref}/{config.CORGIS_PATH}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as resp:
        dest.write_bytes(resp.read())
    return ref


def monthly_sample(days: list[str]) -> list[str]:
    """Keep the last available daily list of each calendar month."""
    last: dict[str, str] = {}
    for d in sorted(x for x in days if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)):
        last[d[:7]] = d
    return list(last.values())


def fetch_rtb(ref: str = config.RTB_COMMIT) -> str:
    """Sparse-checkout profiles and one daily list per month, then compact them.

    Daily lists are the ground truth for who was a billionaire when. One list
    per month (~85 files) is enough for the analysis and keeps the download
    under 100 MB instead of the archive's ~2 GB.
    """
    config.DATA_RAW.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _run(["git", "init", "-q"], repo)
        _run(["git", "remote", "add", "origin", f"https://github.com/{config.RTB_REPO}.git"], repo)
        _run(["git", "fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", ref], repo)
        # Tree listings need no blobs, so this is cheap.
        days = [p.rsplit("/", 1)[-1] for p in
                _run(["git", "ls-tree", "--name-only", "FETCH_HEAD", "api/list/rtb/"], repo).splitlines()]
        months = monthly_sample(days)
        patterns = [f"api/profile/*/{f}" for f in config.RTB_FILES] + ["api/updated"]
        patterns += [f"api/list/rtb/{d}" for d in months]
        _run(["git", "sparse-checkout", "set", "--no-cone", *patterns], repo)
        _run(["git", "checkout", "-q", "FETCH_HEAD"], repo)
        commit = _run(["git", "rev-parse", "HEAD"], repo)
        updated = (repo / "api" / "updated").read_text().strip()
        n_profiles = compact_profiles(repo / "api" / "profile", config.RTB_RAW)
        n_rows = compact_lists(repo / "api" / "list" / "rtb", months, config.RTB_LISTS_RAW)
    _write_sources(rtb={"commit": commit, "upstream_updated": updated, "profiles": n_profiles,
                        "monthly_lists": len(months), "list_rows": n_rows,
                        "first_list": months[0], "last_list": months[-1]})
    return commit


def compact_profiles(profile_dir: Path, dest: Path) -> int:
    n = 0
    with gzip.open(dest, "wt", encoding="utf-8") as out:
        for profile in sorted(profile_dir.iterdir()):
            if profile.name.startswith("_") or not profile.is_dir():
                continue
            record = {"uri": profile.name}
            for name in config.RTB_FILES:
                f = profile / name
                record[name] = json.loads(f.read_text()) if f.exists() else None
            out.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return n


LIST_FIELDS = ("date", "uri", "name", "rank", "net_worth_m", "gender", "age", "citizenship",
               "industry", "source")


def compact_lists(list_dir: Path, days: list[str], dest: Path) -> int:
    n = 0
    with gzip.open(dest, "wt", encoding="utf-8", newline="") as out:
        w = csv.writer(out)
        w.writerow(LIST_FIELDS)
        for day in days:
            data = json.loads((list_dir / day).read_text())
            for p in data["list"]:
                w.writerow([day, p["uri"], p.get("name"), p.get("rank"), p.get("networth"),
                            p.get("gender"), p.get("age"), p.get("citizenship"),
                            ";".join(p.get("industry") or []), ";".join(p.get("source") or [])])
                n += 1
    return n


def _write_sources(**entries) -> None:
    path = config.SOURCES_JSON
    data = json.loads(path.read_text()) if path.exists() else {}
    data.update(entries)
    data["fetched_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def fetch_all(latest: bool = False) -> None:
    if shutil.which("git") is None:
        raise SystemExit("git is required to fetch the real-time archive")
    corgis_ref = "master" if latest else config.CORGIS_COMMIT
    rtb_ref = "main" if latest else config.RTB_COMMIT
    print(f"fetching CORGIS historical lists @ {corgis_ref[:12]}")
    fetch_corgis(ref=corgis_ref)
    _write_sources(corgis={"commit": corgis_ref, "path": config.CORGIS_PATH})
    print(f"fetching real-time profiles @ {rtb_ref[:12]} (a few minutes)")
    commit = fetch_rtb(ref=rtb_ref)
    print(f"done: rtb commit {commit[:12]}")
