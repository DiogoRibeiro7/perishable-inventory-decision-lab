# Override Reason Taxonomy

| Code | Label | Category | Data signal | Blame-safe interpretation |
| --- | --- | --- | --- | --- |
| `back_room_stock` | Back-room stock not reflected | Inventory | `stock_count_gap` | The workflow hid available stock from the system. |
| `display_build` | Display or endcap build | Merchandising | `display_calendar` | The recommendation lacked local display context. |
| `local_event` | Local event demand | Demand | `local_event_calendar` | Local demand context was not represented in the data. |
| `supplier_constraint` | Supplier or delivery constraint | Supply | `supplier_exception` | Supply constraints changed after planning data was captured. |
| `case_pack_issue` | Case-pack or storage issue | Operations | `constraint_master` | Constraint data did not match physical handling. |
| `quality_issue` | Quality or shelf-life concern | Freshness | `quality_log` | Product condition changed the useful inventory quantity. |
| `substitution` | Expected substitution effect | Assortment | `substitution_group` | Nearby products affected expected demand. |
| `promotion_change` | Promotion changed | Commercial | `promotion_revision` | Commercial plans changed after the feature snapshot. |
| `trust_review` | Needs review before use | Trust | `review_flag` | The workflow requires human confirmation for this case. |

Reason codes should be optional for staff when the workflow is under time pressure, but required for release analysis when an override is saved.
