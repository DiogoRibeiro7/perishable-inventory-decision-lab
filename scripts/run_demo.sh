#!/usr/bin/env bash
set -euo pipefail

poetry run perishable-lab demo \
  --days 240 \
  --stores 5 \
  --products 16 \
  --seed 42 \
  --output-dir artifacts/demo
