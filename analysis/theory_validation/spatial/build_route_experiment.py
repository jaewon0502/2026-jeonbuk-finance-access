"""Build new route matrices in a staging directory using the validated graph."""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import run_spatial_validation as spatial
import build_jeonbuk_route_scenario as builder


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pbf", type=Path, required=True)
    parser.add_argument("--boundaries", type=Path, required=True)
    parser.add_argument("--access", type=Path, required=True)
    parser.add_argument("--outlets", type=Path, required=True)
    parser.add_argument("--venues", type=Path, default=spatial.ROOT / "data/processed/venues_jeonbuk.csv")
    parser.add_argument("--config", type=Path, default=spatial.ROOT / "config/jeonbuk_route_default.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path(__file__).parent / "cache")
    parser.add_argument("--analysis-date", default=datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat())
    args = parser.parse_args()
    stage = args.output_dir.resolve()
    if stage == (spatial.ROOT / "data/processed").resolve():
        raise ValueError("experimental outputs must not overwrite submitted processed data")
    access = spatial.read_csv(args.access)
    if any(row["origin_variant"] != "submitted_internal" or row["origin_inside_boundary"] != "Y" for row in access):
        raise ValueError("route experiment expects validated submitted internal origins")
    stage.mkdir(parents=True, exist_ok=True)
    for source, name in ((args.access, "access_road.csv"), (args.outlets, "outlets_validated.csv"), (args.venues, "venues_jeonbuk.csv")):
        destination = stage / name
        if source.resolve() != destination:
            shutil.copyfile(source, destination)
    # These fields are explanatory only. Do not carry old cluster claims into a
    # changed outlet pool without rerunning the cluster analysis.
    spatial.write_csv(stage / "access_typology.csv", [{"code": row["code"], "cluster_label": "not_recomputed_for_validation", "rule_type": "not_recomputed_for_validation"} for row in access])
    config = json.loads(args.config.read_text(encoding="utf-8"))
    config["scenario_id"] += "_theory_validation"
    config["analysis_date"] = args.analysis_date
    config_path = stage / "experiment_config.json"
    spatial.write_json(config_path, config)
    graph, graph_manifest = spatial.load_graph(args.pbf, args.boundaries, args.cache_dir)
    forward_offsets, forward_neighbors = builder.transpose_unweighted_csr(graph["offsets"], graph["neighbors"])
    context = {
        "lats": graph["lats"], "lons": graph["lons"], "offsets": graph["offsets"],
        "neighbors": graph["neighbors"], "weights": graph["weights"],
        "forward_offsets": forward_offsets, "forward_neighbors": forward_neighbors,
        "grid": graph["grid"], "nearby_nodes": spatial.road.nearby_nodes,
        "max_snap_km": spatial.road.MAX_SNAP_KM,
    }
    spatial.write_json(stage / "roadnet_metadata.json", {
        "pbf_md5": spatial.road.md5(args.pbf), "pbf_sha256": graph_manifest["inputs"]["pbf_sha256"],
        "boundary_sha256": graph_manifest["inputs"]["boundary_sha256"],
        "graph_manifest": graph_manifest,
    })
    builder.DATA_OUT = stage
    builder.CONFIG_FILE = config_path
    builder.OUTPUT_FILE = stage / "jeonbuk_route_scenario.json"
    builder.load_graph_context = lambda: context
    result = builder.main()
    output = json.loads(builder.OUTPUT_FILE.read_text(encoding="utf-8"))
    output["validation_provenance"] = {
        "graph": graph_manifest,
        "source_access_sha256": spatial.sha256(args.access),
        "source_outlets_sha256": spatial.sha256(args.outlets),
        "source_venues_sha256": spatial.sha256(args.venues),
        "source_config_sha256": spatial.sha256(args.config),
        "builder_sha256": spatial.sha256(spatial.ROOT / "src/build_jeonbuk_route_scenario.py"),
        "engine_sha256": spatial.sha256(spatial.ROOT / "src/route_scenario.py"),
        "wrapper_sha256": spatial.sha256(Path(__file__)),
        "typology_recomputed": False,
        "dashboard_updated": False,
        "purpose": "frozen matrices for controlled route-method comparison",
    }
    spatial.write_json(builder.OUTPUT_FILE, output)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
