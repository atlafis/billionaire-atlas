"""Command line: ``python -m billionaires {fetch,build,analyze,all}``."""

from __future__ import annotations

import argparse
import time

from . import analysis, build, config, report, sources


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="billionaires", description=__doc__)
    parser.add_argument("command", choices=["fetch", "build", "analyze", "all"])
    parser.add_argument("--latest", action="store_true",
                        help="fetch the newest data instead of the pinned snapshot")
    args = parser.parse_args(argv)

    t0 = time.time()
    if args.command in ("fetch", "all"):
        sources.fetch_all(latest=args.latest)
    if args.command in ("build", "all"):
        if not config.RTB_RAW.exists():
            raise SystemExit("raw data missing: run `python -m billionaires fetch` first")
        build.build_all()
    if args.command in ("analyze", "all"):
        results = analysis.run_all()
        report.write(results)
        print(f"wrote {config.REPORT.relative_to(config.ROOT)} and "
              f"{len(list(config.FIGURES.glob('*.png')))} figures")
    print(f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
