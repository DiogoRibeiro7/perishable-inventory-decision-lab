# Complementary decision-science studies

The main Python package solves retail **demand forecasting and replenishment**.
Studies in this directory are independently executable analyses of related
perishable-inventory decisions. They are not imported by `perishable_lab` and
their synthetic results are not evidence of commercial lift.

| Study | Decision | Language | Reproduction |
|---|---|---|---|
| [Orange storage and sale timing](orange_storage_decision/) | Sell now, hold, or inspect before selling a mixed-maturity orange lot | Base R | See the study [quickstart](orange_storage_decision/README.md#run-the-demonstration) and [protocol](orange_storage_decision/PROTOCOL.md) |

The orange study preserves its simulation records, negative findings and
research limits. Its extraction from `ds-projects-portfolio` is documented in
the [migration record](orange_storage_decision/MIGRATION.md).
