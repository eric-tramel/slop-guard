.DEFAULT_GOAL := help

UV ?= uv
UV_RUN ?= $(UV) run --group dev
PACKAGE ?= slop_guard

.PHONY: help sync fix format format-check lint typecheck test coverage check build verify-wheel clean

help:
	@printf "Available targets:\n"
	@printf "  make sync          Install project and dev dependencies with uv\n"
	@printf "  make fix           Apply import/lint fixes and reformat source files\n"
	@printf "  make format        Format tracked Python sources\n"
	@printf "  make format-check  Check formatting without modifying files\n"
	@printf "  make lint          Run Ruff lint checks\n"
	@printf "  make typecheck     Run ty over src/ and tests/\n"
	@printf "  make test          Run the pytest suite\n"
	@printf "  make coverage      Run pytest with coverage enforcement\n"
	@printf "  make check         Run formatting, lint, type, and coverage checks\n"
	@printf "  make build         Build source and wheel distributions\n"
	@printf "  make verify-wheel  Assert the built wheel ships slop_guard/py.typed\n"
	@printf "  make clean         Remove local build and tool caches\n"

sync:
	$(UV) sync --group dev

fix:
	$(UV_RUN) ruff check src tests --fix
	$(UV_RUN) ruff format src tests

format:
	$(UV_RUN) ruff format src tests

format-check:
	$(UV_RUN) ruff format --check src tests

lint:
	$(UV_RUN) ruff check src tests

typecheck:
	$(UV_RUN) ty check --error-on-warning

test:
	$(UV_RUN) pytest

coverage:
	$(UV_RUN) pytest --cov=$(PACKAGE) --cov-report=term-missing

check: format-check lint typecheck coverage

build:
	$(UV) build

verify-wheel: build
	$(UV_RUN) python -c 'from pathlib import Path; import zipfile; wheels = sorted(Path("dist").glob("*.whl")); assert wheels, "No wheel found in dist/"; wheel = wheels[-1]; names = set(zipfile.ZipFile(wheel).namelist()); target = "slop_guard/py.typed"; assert target in names, f"{target} missing from {wheel.name}"; print(f"verified {target} in {wheel.name}")'

clean:
	rm -rf .coverage .pytest_cache .ruff_cache build dist htmlcov
