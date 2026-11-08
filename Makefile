PY ?= python

.PHONY: install fetch build analyze all test lint

install:        ## install the package and dev tools into the current environment
	$(PY) -m pip install -e ".[dev]"

fetch:          ## download the pinned raw data (~100 MB, a few minutes)
	$(PY) -m billionaires fetch

build:          ## raw data -> data/processed/*.csv
	$(PY) -m billionaires build

analyze:        ## processed data -> reports/figures/*.png and reports/findings.md
	$(PY) -m billionaires analyze

all: fetch build analyze

test:
	$(PY) -m pytest -q

lint:
	ruff check .
