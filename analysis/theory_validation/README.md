# Report validation experiments

This directory supports the final Form 12 report and the revised dashboard.
The original processed submission inputs remain under `data/processed`.
The dashboard now uses the frozen expanded inputs and comparison results here.
Final calculations use the October 11, 2026 road graph for both the original
outlet pool and the additive outlet scenario.

## Inputs and source limits

- `inputs/input_manifest.json` records the original commit, recovered boundary
  hash and the common road version. The original August PBF was not available.
- `outlets/` contains official NH and CU query records, manifests and collection
  scripts. Raw responses remain locally under `outlets/raw/`.
- `inputs/outlet_expansion_audit.json` and `integration_checks.json` record scope
  decisions and preservation of all original outlet fields.
- Additions are current official branch listings treated as assumed open. They
  do not establish August presence, current hours or access to every service.
- Border collection covers NH and regional CU records in the query rectangle
  intersected with a 20 km province-boundary buffer. It is not a census of all
  financial providers. The CU source has two invalid-coordinate records.

## Reproduction

Run from the repository root in a Python environment with `requirements.txt` in
this directory. Restore the boundary with
`git show 655e470:data/raw/hjd2026.geojson` and retrieve the exact PBF URL recorded
in the input manifest. Verify hashes before calculation. Raw and graph cache
files are ignored because they are large. Current directory queries may change;
use the retained CSV snapshots to reproduce these results.

1. Run `analysis/theory_validation/prepare_outlets.py`.
2. Run `spatial/run_spatial_validation.py` with the frozen baseline and expanded
   outlet CSVs, recovered boundary, common PBF and `data/processed/access_road.csv`.
   Final outputs belong in `spatial/results/`.
3. Run `spatial/build_route_experiment.py` with final expanded internal-point
   access and outlet files. Route matrices must be rebuilt because targets,
   candidate sites and depots can change.
4. Run `comparison/run_comparison.py` on the generated scenario JSON. All methods
   share candidates, matrices and constraints. The main comparison fixes a
   target-count allocation before inspecting solver outcomes.

See each subdirectory README for command details. `smoke_original_input/`,
`baseline_preflight/` and `nh_results/` are intermediate diagnostic runs, not
the final expanded-input comparison.

## Interpretation

Distances and coverage describe administrative representative-point proxies.
They are not measured travel time or resident coverage. Centroid sensitivity
tests geometry only. Existing cluster labels are not transferred as newly
validated cluster findings. Prototype routes retain assumed depot access,
venue permission, opening windows, service duration and uniform speed.
