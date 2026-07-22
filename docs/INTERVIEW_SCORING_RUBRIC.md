# Interview Scoring Rubric

| Dimension | Strong | Adequate | Weak |
| --- | --- | --- | --- |
| Forecasting | Explains proper scores, calibration, quantile crossing, dependence, and segment limitations. | Explains quantiles and basic metrics. | Treats the forecast as a point estimate or overclaims calibration. |
| Inventory decisions | Derives critical fractile, links service constraints to cumulative demand, and explains shelf-life state. | Describes waste versus availability trade-off. | Optimizes forecast accuracy without decision consequences. |
| Data realism | Names product identity, censoring, hidden inventory, late data, supplier reliability, and event timing. | Names some data quality issues. | Assumes clean sales data is true demand. |
| Evaluation | Separates forecast metrics, simulator evidence, offline policy checks, and field experiments. | Discusses backtesting. | Claims synthetic results prove live impact. |
| Production judgement | Covers idempotent jobs, atomic publication, rollback, monitoring, and role separation. | Covers deployment basics. | Ignores failure modes or partial publication. |
| Store operations | Translates uncertainty into workflow choices and treats overrides as evidence, not blame. | Mentions users and overrides. | Asks staff to validate mathematical details. |
| Honesty | Clearly states assumptions, limitations, and unproven claims. | Mentions limitations when asked. | Overstates what the repository proves. |

## Suggested Scoring

```text
5: Ready for senior/founding scope; gives precise answers and names limits.
4: Strong, with minor gaps in production or experimentation detail.
3: Solid technical base, needs deeper operational or causal reasoning.
2: Understands components but cannot connect forecast to decision risk.
1: Overclaims results or misses core uncertainty and safety issues.
```
