.PHONY: help init init-dev lint bandit black build install uninstall tests clean clean-build clean-pyc

.DEFAULT: help

## Install requirements
init:
	poetry install --without dev --no-root --no-interaction --no-ansi

## Install requirements-dev
init-dev:
	poetry install --only dev --no-root --no-interaction --no-ansi

## Check python lint with flake8
lint:
	flake8 --config .flake8 wikiform/
	flake8 --config .flake8 tests/

## Check python code with bandit
bandit:
	bandit -r wikiform/ -c pyproject.toml
	bandit -r tests/ -c pyproject.toml

## Check python code with black
black:
	black wikiform/ --config pyproject.toml --diff --color
	black tests/ --config pyproject.toml --diff --color

## Create dist package (poetry)
build: clean
	poetry build

## Install wheel package
install: clean build
	pip3 install dist/*.whl

## Uninstall wikiform
uninstall:
	pip3 uninstall -y wikiform

## Python unit tests
tests:
	pytest tests -v -l -p no:warnings --disable-warnings

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
