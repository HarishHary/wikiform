.PHONY: help init init-dev lint bandit black build install uninstall tests clean clean-build clean-pyc

.DEFAULT: help

# Pin the interpreter for every uv call so a stale/unparsable .python-version
# (e.g. a pyenv virtualenv name) cannot break `make` targets. Override with UV_PYTHON=...
export UV_PYTHON ?= 3.14

## Install runtime requirements only
init:
	uv sync --no-dev

## Install runtime + dev requirements
init-dev:
	uv sync

## Check python lint with flake8
lint:
	uv run flake8 --config .flake8 wikiform/
	uv run flake8 --config .flake8 tests/

## Check python code with bandit
bandit:
	uv run bandit -r wikiform/ -c pyproject.toml
	uv run bandit -r tests/ -c pyproject.toml

## Check python code with black
black:
	uv run black wikiform/ --config pyproject.toml --diff --color
	uv run black tests/ --config pyproject.toml --diff --color

## Create dist package (uv build)
build: clean
	uv build

## Install wheel package as a uv tool
install: clean build
	uv tool install --force dist/*.whl

## Uninstall wikiform
uninstall:
	uv tool uninstall wikiform

## Python unit tests
tests:
	uv run pytest tests -v -l -p no:warnings --disable-warnings

## Deep clean
clean: clean-build clean-pyc

## Clean build
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr .pytest_cache/
	rm -fr output/
	rm -fr .ruff_cache/
	rm -fr .coverage
	rm -fr coverage_html_report/

## Clean pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +

## This help screen
help:
	@printf "Available targets:\n\n"
	@awk '/^[a-zA-Z\-\0-9%:\\]+/ { \
	helpMessage = match(lastLine, /^## (.*)/); \
	if (helpMessage) { \
		helpCommand = $$1; \
		helpMessage = substr(lastLine, RSTART + 3, RLENGTH); \
		gsub("\\\\", "", helpCommand); \
		gsub(":+$$", "", helpCommand); \
		printf "  \x1b[32;01m%-15s\x1b[0m %s\n", helpCommand, helpMessage; \
		} \
	} \
	{ lastLine = $$0 }' $(MAKEFILE_LIST) | sort -u
	@printf "\n"
