# Assumption-To-Evidence Register

| Assumption id | Assumption | Workflow problem | Evidence status | Evidence reference | Owner |
| --- | --- | --- | --- | --- | --- |
| `A-001` | Back-room stock is often unavailable to the ordering workflow. | Stock not visible at cutoff creates avoidable over-orders. | Measured | Store visit and override-rate report | Operations |
| `A-002` | Promotion changes can arrive after feature snapshots. | Stores need a review path for promotion-sensitive rows. | Observed repeatedly | Customer success ticket grouping | Commercial |
| `A-003` | Supplier exceptions affect recommended quantities after planning data is captured. | Stores need explanation when supplier fill or delivery timing changes. | Measured | Supplier reliability report | Operations |
| `A-004` | Case-pack and storage constraints can differ from master data. | Recommendations can be infeasible to receive or store. | Observed repeatedly | Store observation template | Product |

Evidence status values:

- Untested.
- Observed once.
- Observed repeatedly.
- Measured.
- Validated.

Product or data changes should not proceed from untested or one-off observations unless explicitly labelled exploratory.
