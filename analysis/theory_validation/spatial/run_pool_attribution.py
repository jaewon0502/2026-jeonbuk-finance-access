"""Evaluate an additive subgroup against the common-road internal baseline."""

import argparse
import json
from pathlib import Path

import run_spatial_validation as spatial


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--outlets", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).parent / "cache")
    args = parser.parse_args()
    reference = json.loads((args.reference_dir / "summary.json").read_text(encoding="utf-8"))
    paths = {}
    for name in ("pbf", "boundaries", "access", "outlets_baseline"):
        record = reference["inputs"][name]
        paths[name] = Path(record["path"])
        if spatial.sha256(paths[name]) != record["sha256"]:
            raise RuntimeError(f"reference input changed: {name}")
    baseline = spatial.load_outlets(paths["outlets_baseline"])
    expanded = spatial.load_outlets(args.outlets)
    spatial.validate_additive_pool(baseline, expanded)
    graph, manifest = spatial.load_graph(paths["pbf"], paths["boundaries"], args.cache_dir)
    if manifest["inputs"] != reference["graph"]["inputs"]:
        raise RuntimeError("attribution graph differs from reference graph")
    baseline_path = args.reference_dir / "access_baseline_internal.csv"
    if spatial.sha256(baseline_path) != reference["outputs"][baseline_path.name]:
        raise RuntimeError("reference baseline CSV changed")
    origins = spatial.origin_rows(spatial.read_csv(paths["access"]), paths["boundaries"])["internal"]
    routes, stats = spatial.shortest_paths(graph, expanded)
    rows = spatial.evaluate_origins(graph, origins, expanded, routes, "attribution_subgroup")
    comparisons, comparison_summary = spatial.pair_comparison(spatial.read_csv(baseline_path), rows, True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    spatial.write_csv(args.output_dir / "access_internal.csv", rows)
    spatial.write_csv(args.output_dir / "outlet_effect_internal.csv", comparisons)
    summary = {
        "outlets_path": str(args.outlets.resolve()), "outlets_sha256": spatial.sha256(args.outlets),
        "reference_summary_sha256": spatial.sha256(args.reference_dir / "summary.json"),
        "reference_baseline_sha256": spatial.sha256(baseline_path), "graph": manifest,
        "runner_sha256": spatial.sha256(Path(__file__)),
        "spatial_functions_sha256": spatial.sha256(Path(spatial.__file__)),
        "pool_stats": stats, "cell": spatial.cell_summary(rows), "comparison": comparison_summary,
    }
    spatial.write_json(args.output_dir / "summary.json", summary)
    print(json.dumps({"cell": summary["cell"], "comparison": summary["comparison"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
