# Product And Data Hypotheses

| Priority | Hypothesis | Workflow problem | Required data | Measurable outcome | Acceptance criteria | Validation |
| --- | --- | --- | --- | --- | --- | --- |
| High | Add back-room stock visibility to order review. | Stock not visible at cutoff creates avoidable over-orders. | `stock_count_gap`, `override_reason`, count timestamp | Back-room-stock override rate | Override rate drops by 20 percent in pilot stores | Before/after pilot with matched stores |
| High | Flag promotion-sensitive recommendations for review when commercial data is revised after cutoff. | Promotion revisions make recommendations hard to trust. | `promotion_revision`, `event_known_at`, recommendation id | Review acceptance and fewer promotion-change overrides | Promotion-change override rate drops by 15 percent without waste increase | Shadow comparison followed by limited pilot |
| Medium | Add supplier exception explanation to recommendation output. | Supplier changes arrive after planning data is captured. | `supplier_exception`, fill rate, delivery delay | Fewer support tickets for unexplained low or high orders | Supplier-related tickets drop by 10 percent | Ticket analysis and customer success review |
| Medium | Validate case-pack and storage constraints with store review. | Recommendations can be infeasible to receive or store. | `constraint_master`, override reason, capacity observation | Constraint violation rate | Zero known infeasible recommendations in pilot | Fixture and pilot validation |

Each hypothesis must link to an observed workflow problem, measurable outcome, required data, and validation method before engineering work starts.
