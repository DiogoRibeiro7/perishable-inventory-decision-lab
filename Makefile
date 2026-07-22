.PHONY: install demo test lint typecheck hygiene quality clean

install:
	poetry install

demo:
	poetry run perishable-lab demo --output-dir artifacts/demo

test:
	poetry run pytest

lint:
	poetry run ruff check .

typecheck:
	poetry run mypy src

hygiene:
	poetry run python scripts/repo_hygiene.py

quality: lint typecheck hygiene test

clean:
	rm -rf artifacts .coverage .pytest_cache .mypy_cache .ruff_cache
