# Validation Evidence

The repository was validated in the build environment with:

```bash
ruff check .
mypy src
PYTHONPATH=src pytest -q
python -m compileall -q src tests
```

Results at packaging time:

- Ruff: no issues.
- mypy: strict mode, no issues in 20 source files.
- pytest: 6 tests passed.
- Package coverage: 86%.
- Representative end-to-end run: 180 days, 3 stores, 8 products, 744 untouched test rows.

The Docker and cloud deployment examples were reviewed structurally but were not executed in this environment because Docker and a configured GCP project were unavailable.
