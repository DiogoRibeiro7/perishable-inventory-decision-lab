# Observability And Incident Response

This runbook lets an operator identify impact, stop publication, activate a safe policy, and reproduce a failed run from immutable logs.

## Monitoring Layers

| Layer | Signals |
| --- | --- |
| Data | Freshness, completeness, duplicates, revisions, schema changes, mapping churn, stock anomalies. |
| Model | Artifact loading, version allow-list, latency, distribution drift, forecast bias, coverage after outcomes, fallback rate. |
| Decision | Missing recommendations, constraint violations, order jumps, override rate, fill rate, waste, stockouts, supplier exceptions. |
| System | Job status, retries, partition completeness, storage writes, publication state, cost, SLA. |

## Alert Contract

Every alert includes:

- Severity.
- Owner.
- Threshold and direction.
- Minimum sample.
- Deduplication key.
- Context links.
- Safe fallback.
- Closure condition.

Alerts with samples below the configured minimum are suppressed to avoid paging on noisy small samples. Automatic rollback is allowed only for deterministic, reversible conditions such as corrupted artifacts, partial publication writes, invalid inventory snapshots, broken product mapping, and bad policy versions.

## Immediate Triage

1. Open the dashboard link in the alert context.
2. Check the deduplication key and affected retailer, date, store, product, supplier, or policy.
3. Stop publication by holding the active pointer swap.
4. If the alert has automatic rollback, revert to the previous valid batch or safe incumbent policy.
5. Confirm store-facing files do not expose a partial batch.
6. Save structured logs, run manifest, feature-set hash, active pointer, and publication manifest.
7. Continue only after the closure condition is met.

## Scenario Runbooks

| Scenario | Impact check | Fallback | Closure |
| --- | --- | --- | --- |
| Stale sales data | Missing or delayed sales partitions by business date. | Hold publication. | Freshness below six hours for affected date. |
| Broken product mapping | Mapping failure rate or mapping churn spike. | Safe incumbent policy. | Failure rate below two percent and identity diff approved. |
| Promotion feed outage | Event feed age and missing revised events. | Manual review of promotion-sensitive rows. | Feed catches up and revised feature snapshot is published. |
| Invalid inventory snapshots | Negative, impossible, stale, or duplicated counts. | Safe incumbent policy. | Invalid snapshot rate below one percent for two runs. |
| Model artifact corruption | Artifact hash mismatch or load failure. | Previous valid batch. | Hash matches manifest after clean redeploy. |
| Forecast undercoverage | Coverage below threshold after outcomes arrive. | Manual review and calibration hold. | Coverage returns above threshold. |
| Supplier disruption | Supplier exception rate or fill-rate break. | Manual review with store operations. | Exceptions return below threshold and communications are sent. |
| Partial warehouse write | Partition completeness below one. | Previous valid batch. | Expected partitions complete and active pointer unchanged. |
| Cloud Run timeout | Timeout count above zero. | Hold publication. | Job succeeds with same deterministic job id. |
| Airflow retry storm | Retry count above threshold. | Hold publication. | Retry count stops increasing and downstream tasks reconcile. |
| Bad policy version | Active policy not on allow-list. | Previous valid batch. | Active pointer reverted and allow-list corrected. |

## Structured Logs

Each alert evaluation is written as a structured event with:

- Event id.
- UTC timestamp.
- Run id.
- Event type.
- Payload.
- Previous event hash.

Replay verifies the hash chain and reconstructs firing alerts. A broken chain means the run cannot be used for final incident evidence until raw logs are recovered.

## Dashboard Specification

Panels must cover the four monitoring layers and include links to source partitions, model manifest, decision batch, publication state, cost view, and run logs.

## Service Objectives

| Name | Target | Window | Measurement |
| --- | ---: | --- | --- |
| Daily publication | 99% | 30d | Complete batch published before store cutoff. |
| Data freshness | 99.5% | 30d | Core data available within freshness threshold. |
| Rollback readiness | 100% | 30d | Previous valid batch exists for every active batch. |
| Alert noise | 95% | 30d | Page alerts meet minimum sample and dedup rules. |

## Game-Day Drill

1. Freeze publication for the drill retailer and date.
2. Inject stale sales data into the metrics fixture.
3. Confirm the stale-sales alert fires once after minimum sample is met.
4. Activate hold-publication fallback.
5. Replay logs and verify the event hash chain.
6. Restore healthy metrics and confirm closure condition.
7. Record impact, detection time, fallback action, and recovery time.

## Post-Incident Template

```text
Incident:
Start:
End:
Owner:
Severity:
Affected retailer/date/store/product:
Customer or store impact:
Detection source:
Fallback action:
Rollback batch id:
Run id:
Feature-set hash:
Publication manifest:
Root cause:
What worked:
What failed:
Corrective actions:
Closure evidence:
```
