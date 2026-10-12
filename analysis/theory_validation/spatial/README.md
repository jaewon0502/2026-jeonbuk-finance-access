# Spatial validation

The runner compares the submitted outlet inventory with an additive inventory.
It evaluates both at the exact submitted internal coordinates and at full
administrative polygon area centroids. All four cells use the same road graph.
The centroid is calculated in EPSG:5179 over every component and subtracts holes.
Outside centroids remain diagnostics and never become eligible route origins.

The expanded inventory must retain every original outlet ID and preserve its
coordinates and finance status. Existing source problems are not silently fixed
inside an addition experiment. Additional records need the same columns used by
the original outlet CSV, including `outlet_id`, `name`, `type`, `lat`, `lon` and
`finance_open`. Their source and date evidence is maintained by the outlet audit.

Outputs preserve unrounded distances for thresholds. P1 means distance > 5 km.
P2 means distance > 3 km and <= 5 km. Quality and origin validity are independent
flags. Neither representative point is a population exposure estimate.

```
.venv/bin/python analysis/theory_validation/spatial/test_spatial_validation.py
.venv/bin/python analysis/theory_validation/spatial/run_spatial_validation.py \
  --pbf <common-road.pbf> --boundaries <hjd2026.geojson> \
  --access <frozen-access_road.csv> \
  --outlets-baseline <frozen-outlets_validated.csv> \
  --outlets-expanded <expanded-outlets.csv> \
  --output-dir analysis/theory_validation/spatial/results
```

The graph cache checks source file hashes, road-builder code hashes and package
version. Its local pickle is loaded only after its hash and manifest match.
Do not replace it with an externally supplied pickle.

`access_expanded_internal.csv` is the compatible road-access input for the route
experiment. Regenerate candidate selection, depots and route matrices from this
input. Submitted typology labels are not recalculated by this spatial runner.

One explicit fallback correction is confined to these experiments: reachable
nodes are ordered by connector distance then node index. The legacy road runner
takes the first node-index-sorted reachable candidate. Such fallback rows remain
non-primary and are excluded from route targets in both versions. An unchanged
nearest-node snap and nonincreasing distance are asserted for additive-pool
comparisons whose two cells are primary.

`submitted_vs_common_road_baseline.csv` is a version/precision diagnostic.
Only the four factorial cells support the outlet and origin effect claims.
`threshold_sensitivity.csv` varies the lower threshold across 2.5/3/3.5 km and the
upper across 4/5/6 km. These are scenario checks rather than calibrated thresholds.

`build_route_experiment.py` accepts `--pbf`, `--boundaries`, `--access`, `--outlets`
and `--output-dir`. Pass the expanded internal result as `--access`. It stages
compatible CSV inputs and invokes the existing builder with the same cached
graph. Old typology labels are replaced by `not_recomputed_for_validation`.
The resulting scenario contains matrices and default results for the comparison
runner. This does not update the published dashboard or prove field readiness.

Implementation references:

- [Shapely area-weighted centroid](https://shapely.readthedocs.io/en/stable/reference/shapely.centroid.html)
- [Shapely coordinate transforms](https://shapely.readthedocs.io/en/stable/reference/shapely.transform.html)
- [pyproj Transformer and axis order](https://pyproj4.github.io/pyproj/stable/api/transformer.html)
- Existing directed road and route contracts in `src/build_roadnet.py` and
  `src/build_jeonbuk_route_scenario.py`.
