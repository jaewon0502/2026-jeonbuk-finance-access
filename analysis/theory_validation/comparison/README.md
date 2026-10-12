# Controlled comparison protocol

This directory contains experimental code only. It does not change the submitted solver, dashboard or processed inputs.

## Inputs and sequence

Run the final experiment only after the financial-outlet audit and representative-point analysis have frozen their scenario inputs. The input is the existing `jeonbuk_route_scenario.json` contract or its top-level `engine_input` object. Every zone must have disjoint target IDs and complete directed distance and travel-time matrices. Candidate selection, depots, time windows, service duration, operating hours and travel assumptions are inherited unchanged.

`smoke_original_input/` uses the saved submission scenario. It is a runner check, not an updated-accessibility result.

## Routing comparison

The three methods are:

1. Existing nearest-feasible greedy from `src/route_scenario.py`.
2. Priority-aware nearest-feasible greedy. Each feasible next candidate is ranked by newly covered P1 targets, newly covered P2 targets, total newly covered targets, travel time from the current node and candidate ID. Already covered targets are not counted again. Candidates adding no new targets are skipped.
3. Existing exact subset DP from `src/route_scenario.py`.

The primary experiment uses all three methods with the same fixed zone allocation. It repeats for stop caps 3, 4 and 5. All other parameters remain fixed. The reference allocation is chosen before examining routing outcomes: apply the existing minimum quota and upper bounds, then distribute remaining route-days in proportion to each zone's unique target count using bounded largest remainders. Fractional ties use zone ID. If a bound is reached, repeat over zones with remaining room. The reference is checked to remain identical across stop caps.

Compare P1 coverage first, P2 coverage second, total unique targets third, travel plus waiting time fourth and the longest route last. Distance alone is not the optimization objective. Equal resource ceilings do not require equal actual resource usage.

## Allocation comparison

For priority greedy and exact DP separately, build the outcome table for every allowed zone capacity. Apply the existing province allocation DP to that method's own outcomes. The resulting 2 x 2 comparison separates routing method from allocation policy. The optimized allocation may differ between solvers because their outcome tables differ.

An additional conditional comparison runs nearest and priority greedy under the exact solver's selected allocation. This reproduces the allocation policy used by the original repository. It must not be interpreted as an independent end-to-end baseline.

## Evidence and limitations

The JSON contains all route details, allocations, tier coverage, covered and unvisited target IDs, travel distance, travel and waiting time, maximum route duration, allocated and used days, replay violations and runtime measurements. The CSV provides a compact table. Input, engine and runner SHA-256 hashes and the Git commit identify the run. The Git commit does not include uncommitted experimental files, which are identified by their separate hashes.

An independent replay recomputes route times and distances from matrix legs. It checks service windows, return before closing, stop limits, unique candidate visits, zone and province capacity, unique target coverage, unvisited IDs and summary totals. Tests also cover priority tradeoffs, infeasible high-priority candidates, overlapping coverage, deterministic ties, allocation bounds, an exhaustive allocation oracle and parity with the original solver.

Runtime values are single local wall-clock measurements. Selected zone-solve time and all-outcome preparation time are reported separately. They exclude file I/O and allocation/replay overhead. They do not support a statistical speed claim.

Coverage means administrative target coverage. It does not estimate residents served. Field access, real traffic and interzone repositioning remain outside the submitted travel model unless the upstream scenario explicitly upgrades them.

## Commands

From the repository root:

```sh
python3 -m unittest discover -s analysis/theory_validation/comparison -p 'test_*.py' -v
python3 analysis/theory_validation/comparison/run_comparison.py --input data/processed/jeonbuk_route_scenario.json --output analysis/theory_validation/comparison/smoke_original_input --label original_submission_input_smoke_only
```

For the final run, replace the input and output paths and use a label describing the validated input version. Keep the smoke directory separate.
