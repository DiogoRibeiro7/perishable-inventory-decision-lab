# Fixture Catalogue

| Fixture | Location | Failure targeted |
| --- | --- | --- |
| Golden simulation expected output | `tests/fixtures/golden_simulation_expected.csv` | Event ordering, expiry handling, and inventory cost drift. |
| Generated inventory seeds | `tests/test_properties.py` | Negative quantities, demand accounting drift, and non-repeatable replay. |
| Point-in-time examples | `tests/test_feature_store.py` | Late records, daylight-saving boundaries, duplicate versions, and cutoff equality. |
| Publication faults | `tests/test_publication.py` | Partial publication, stale versions, corrupted artifacts, and rollback. |
| Performance small workload | `tests/test_performance.py` | Optimisation parity, chunk row loss, nondeterministic parallel work, and budget drift. |

Tiny hand-computable fixtures are used for decision contracts, point-in-time joins, publication state, and inventory event ordering. Generated examples use explicit `pytest` parameter ids such as `seed=17` so any stochastic failure reports the seed needed for replay.
