# Robust Stochastic Inventory Optimisation

## Scope

The optimisation layer compares transparent heuristics with scenario-based expected-cost and worst-case formulations. It is solver-independent and ships with deterministic exhaustive enumeration for tiny and testable problems.

## Supported Formulations

- Single-period newsvendor quantity with service constraints.
- Age-structured base-stock approximation.
- Sample-average approximation over demand, lead-time, and shelf-life scenarios.
- Worst-case robust optimisation over an uncertainty set.
- Hard case-pack, minimum-order, capacity, and display-stock constraints.

## Guardrails

The optimiser never uses future realised demand or hidden true stock. Candidate quantities are integer and must satisfy hard constraints before the objective is evaluated. Infeasible and timed-out runs return explicit status and fallback metadata.

## Reporting

Each result records solver, version, status, gap, runtime, objective value, order quantity, and fallback reason. Policy reports should compare cost, fill rate, waste, volatility, runtime, violations, and regret under nominal and shifted distributions.
