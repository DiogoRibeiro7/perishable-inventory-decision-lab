# Orange storage study: source and migration record

- **Source repository:** [`DiogoRibeiro7/ds-projects-portfolio`](https://github.com/DiogoRibeiro7/ds-projects-portfolio)
- **Source path:** `projects/orange_storage_decision/`
- **Pinned source snapshot:** [`5eafe111f3a058595f0d2438a9bb0a07b02f5037`](https://github.com/DiogoRibeiro7/ds-projects-portfolio/tree/5eafe111f3a058595f0d2438a9bb0a07b02f5037/projects/orange_storage_decision)
- **Destination path:** `studies/orange_storage_decision/`
- **Migration date:** 2026-11-02
- **Origin:** Diogo Ribeiro's independent synthetic orange sale-timing programme, including the merged adaptive inspection policy from [PR #676](https://github.com/DiogoRibeiro7/ds-projects-portfolio/pull/676).

## Scope

The extraction carries all source R modules, test programs, simulation scripts,
research notes, and **committed synthetic** CSV/PNG reports. It preserves
unfavourable results; no datasets have been silently filtered or recomputed.
Only original-path references and the study entry-page text were updated for
the destination layout. Its original MIT license notice is retained in
[`LICENSE`](LICENSE) alongside this study; the wider Python repository is
Apache-2.0 licensed.

The source Git history remains accessible at the pinned commit. The portfolio
can become a concise link to the destination after the destination migration
passes CI and is merged. This preserves a stable point of reference while
avoiding two active copies of the same scientific code.

## Scientific separation

The R study optimises the sale date of a stored, initially eligible orange
lot under assumed price paths and degradation. The Python package optimises
retail ordering under demand, stockout and shelf-life uncertainty. They are
related decision problems, **not** parts of a single evaluated pipeline.
Importing this study does not integrate the R solver with Python inventory
simulations or validate its synthetic conclusions using real retailers.

## Validation

From the destination repository root:

```sh
cd studies/orange_storage_decision
for test_file in tests/test_*.R; do Rscript "$test_file"; done
Rscript scripts/demo.R
Rscript scripts/run_adaptive_policy.R 20 /tmp/orange-adaptive-check
```

The `Orange Storage Study (R)` GitHub Actions workflow reproduces these checks
without requiring external R packages or datasets.
