.DEFAULT_GOAL := help

UV ?= uv
UV_RUN ?= $(UV) run --group dev
UV_DOCS_RUN ?= $(UV) run --group docs
PACKAGE ?= slop_guard

.PHONY: help sync fix format format-check lint typecheck test coverage check docs-rules docs-serve docs-build docs-check build verify-wheel clean

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
	@printf "  make docs-rules    Regenerate the rule library page from the rule catalog\n"
	@printf "  make docs-serve    Preview the Zensical docs locally\n"
	@printf "  make docs-build    Build the Zensical docs site\n"
	@printf "  make docs-check    Build docs and lint README/docs prose with slop-guard\n"
	@printf "  make build         Build source and wheel distributions\n"
	@printf "  make verify-wheel  Verify wheel typing, scripts, and isolated installation\n"
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

docs-rules:
	$(UV_DOCS_RUN) python -m tools.docs_rules

docs-serve: docs-rules
	$(UV_DOCS_RUN) zensical serve

docs-build: docs-rules
	$(UV_DOCS_RUN) python -m tools.docs_site build

docs-check: docs-build
	$(UV_DOCS_RUN) sg -t 60 README.md $$(find docs -type f -name '*.md' -not -path 'docs/rules/*' | sort)

build:
	$(UV) build

verify-wheel: build
	@set -eu; \
	python=$$($(UV_RUN) python -c 'import sys; print(sys.executable)'); \
	wheel=$$("$$python" -c 'from pathlib import Path; wheels = tuple(Path("dist").glob("*.whl")); assert wheels, "No wheel found in dist/"; print(max(wheels, key=lambda path: (path.stat().st_mtime_ns, path.name)))'); \
	"$$python" -c 'from configparser import ConfigParser; from pathlib import Path; import sys, zipfile; wheel = Path(sys.argv[1]); archive = zipfile.ZipFile(wheel); names = set(archive.namelist()); target = "slop_guard/py.typed"; assert target in names, f"{target} missing from {wheel.name}"; metadata = [name for name in names if name.endswith(".dist-info/entry_points.txt")]; assert len(metadata) == 1, f"expected one entry_points.txt in {wheel.name}, found {len(metadata)}"; parser = ConfigParser(interpolation=None); parser.optionxform = str; parser.read_string(archive.read(metadata[0]).decode("utf-8")); required = ("slop-guard", "sg", "sg-hook"); scripts = parser["console_scripts"] if parser.has_section("console_scripts") else {}; missing = [name for name in required if name not in scripts]; assert not missing, f"console scripts missing from {wheel.name}: {missing}"; archive.close(); print("verified {} and console scripts {} in {}".format(target, ", ".join(required), wheel.name))' "$$wheel"; \
	tmp_root=$$("$$python" -c 'import tempfile; print(tempfile.mkdtemp(prefix="slop-guard-wheel-verify-"))'); \
	cleanup() { "$$python" -c 'import shutil, sys; shutil.rmtree(sys.argv[1], ignore_errors=True)' "$$tmp_root"; }; \
	trap cleanup 0 1 2 15; \
	UV_TOOL_DIR="$$tmp_root/tools" UV_TOOL_BIN_DIR="$$tmp_root/bin" $(UV) tool install --force "$$wheel"; \
	"$$tmp_root/bin/slop-guard" --version; \
	"$$tmp_root/bin/sg" --help; \
	"$$tmp_root/bin/sg-hook" --help

clean:
	rm -rf .coverage .pytest_cache .ruff_cache build dist htmlcov site
