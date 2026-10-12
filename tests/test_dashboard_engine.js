const test = require("node:test");
const assert = require("node:assert/strict");

const data = require("../docs/demo-jeonbuk/data.js");
const mapData = require("../docs/demo-jeonbuk/map-data.js");
const engine = require("../docs/demo-jeonbuk/scenario-engine.js");


test("dashboard bundle covers all Jeonbuk admins and service zones", () => {
  assert.equal(data.admins.length, 243);
  assert.equal(new Set(data.admins.map((row) => row.code)).size, 243);
  assert.equal(new Set(data.admins.map((row) => row.service_zone)).size, 14);
  assert.equal(data.route.engine_input.zones.length, 14);
  assert.equal(data.scope.route_eligible_target_count, 54);
  assert.equal(data.measurement_contract.resident_coverage_available, false);
  assert.equal(data.measurement_contract.population_exposure_valid, false);
  assert.equal(data.measurement_contract.candidate_location_optimization_performed, false);
  assert.equal(data.evidence_summary.stop_cap_sensitivity.length, 3);
  assert.equal(data.evidence_summary.speed_service_sensitivity.length, 0);
  assert.equal(data.outlets.length, 1347);
  assert.equal(data.source_summary.finance_outlet_count, 1347);
  assert.equal(data.source_summary.finance_outlet_listed_count, 1385);
  assert.equal(data.outlets.length, data.source_summary.finance_outlet_count);
  assert.ok(data.outlets.every((row) => row.finance_open === "Y"));
  assert.deepEqual(
    [...new Set(data.outlets.map((row) => row.type))].sort(),
    ["농·축협", "농협은행", "새마을금고", "신협", "우체국", "은행"],
  );
  assert.ok(data.source_as_of.admin);
  assert.ok(data.source_as_of.population_65plus);
  assert.ok(data.source_as_of.outlets);
  assert.ok(data.source_as_of.outlets_retrieved);
  assert.equal(data.source_summary.road_primary_count, 240);
  assert.equal(data.scope.route_quality_deferred_count, 1);
});


test("map bundle contains real boundaries, roads, and directed route geometry", () => {
  assert.equal(mapData.boundaries.length, 243);
  assert.equal(new Set(mapData.boundaries.map((row) => row.code)).size, 243);
  assert.deepEqual(
    [...new Set(mapData.boundaries.map((row) => row.code))].sort(),
    [...new Set(data.admins.map((row) => row.code))].sort(),
  );
  assert.equal(mapData.zone_labels.length, 14);
  assert.ok(mapData.source.major_road_way_count > 10000);
  assert.equal(mapData.route_legs.length, 294);
  assert.ok(mapData.route_legs.every((leg) => leg.path.length >= 2));
  assert.ok(mapData.route_legs.every((leg) => leg.node_sample.length >= 1 && leg.node_sample.length <= 64));
  assert.ok(mapData.source.maximum_matrix_path_delta_km <= 0.002);
  const legs = new Set(mapData.route_legs.map((leg) => `${leg.zone_id}|${leg.origin_id}|${leg.destination_id}`));
  for (const zone of data.route.engine_input.zones) {
    const engineInput = zone.engine_input;
    const nodeIds = Object.keys(engineInput.distance_km);
    for (const origin of nodeIds) {
      for (const destination of nodeIds) {
        if (origin !== destination) assert.ok(legs.has(`${zone.zone_id}|${origin}|${destination}`));
      }
    }
  }
});


test("input controls enforce integer, 15-minute, and 30-minute steps", () => {
  const base = data.sensitivity_presets.find((row) => row.preset_id === "default").parameters;
  assert.throws(
    () => engine.validateParameters({ ...base, vehicle_count: 1.5 }, data.input_controls),
    /정수/,
  );
  assert.throws(
    () => engine.validateParameters({ ...base, service_minutes: 50 }, data.input_controls),
    /15분 단위/,
  );
  assert.throws(
    () => engine.validateParameters({ ...base, operating_start: "09:10" }, data.input_controls),
    /30분 단위/,
  );
});


test("reachable form error branches: end before start, malformed HH:MM, unknown zone, empty zone list", () => {
  const base = data.sensitivity_presets.find((row) => row.preset_id === "default").parameters;
  assert.throws(
    () => engine.validateParameters({ ...base, operating_start: "17:00", operating_end: "09:00" }, data.input_controls),
    /늦어야/,
  );
  assert.throws(
    () => engine.validateParameters({ ...base, operating_start: "9:00" }, data.input_controls),
    /잘못된 시각/,
  );
  assert.throws(
    () => engine.sliceProvinceInput(data.route.engine_input, ["없는시군"]),
    /없는 시·군/,
  );
  const empty = engine.calculate(
    engine.sliceProvinceInput(data.route.engine_input, []),
    base,
    data.input_controls,
  );
  assert.equal(empty.target_count, 0);
  assert.equal(empty.covered_target_count, 0);
  assert.equal(empty.routes.length, 0);
});


test("service cycle control: range check, operating-days cross check, and no effect on coverage", () => {
  const base = data.sensitivity_presets.find((row) => row.preset_id === "default").parameters;
  assert.throws(
    () => engine.validateParameters({ ...base, service_cycle_days: 15 }, data.input_controls),
    /서비스 주기/,
  );
  assert.throws(
    () => engine.validateParameters({ ...base, operating_days_per_cycle: 5, service_cycle_days: 3 }, data.input_controls),
    /서비스 주기를 넘을 수 없습니다/,
  );
  const withCycle = engine.calculate(
    data.route.engine_input,
    { ...base, service_cycle_days: 14 },
    data.input_controls,
  );
  const reference = engine.calculate(data.route.engine_input, base, data.input_controls);
  assert.equal(withCycle.covered_target_count, reference.covered_target_count);
  assert.deepEqual(withCycle.coverage_by_tier, reference.coverage_by_tier);
  assert.equal(withCycle.parameters.service_cycle_days, 14);
});


test("zones with no feasible route in the operating window get zero allocated days", () => {
  const tight = engine.calculate(
    data.route.engine_input,
    { vehicle_count: 3, operating_days_per_cycle: 5, max_stops_per_route: 7, service_minutes: 15, operating_start: "06:00", operating_end: "09:30" },
    data.input_controls,
  );
  assert.ok(tight.zone_allocations.every(
    (zone) => zone.allocated_route_days === 0 || zone.covered_target_count > 0,
  ));
  assert.equal(
    tight.zone_allocations.reduce((sum, zone) => sum + zone.allocated_route_days, 0),
    tight.route_days_used,
  );
  assert.equal(tight.routes.length, tight.route_days_used);
  assert.equal(tight.all_zones_allocated, false);
});


for (const preset of data.sensitivity_presets) {
  test(`${preset.label} browser result matches the Python reference`, () => {
    const actual = engine.calculate(
      data.route.engine_input,
      preset.parameters,
      data.input_controls,
    );
    assert.deepEqual(actual.coverage_by_tier, preset.result.coverage_by_tier);
    assert.equal(actual.covered_target_count, preset.result.covered_target_count);
    assert.equal(actual.route_days_used, preset.result.route_days_used);
    assert.equal(actual.routes.length, actual.route_days_used);
    assert.ok(actual.routes.every((route) => route.stops.length > 0));
    assert.equal(actual.all_zones_allocated, preset.all_zones_allocated);
    assert.ok(Math.abs(actual.totals.travel_km - preset.result.totals.travel_km) < 0.001);
  });
}


test("two-zone slice matches the Python reference solver numerically", () => {
  // 기대값은 src/route_scenario.py의 configure_province + solve_province를
  // 동일한 sliceProvinceInput(남원시, 순창군) 입력과 기본안 파라미터로 실행해 얻었다.
  const preset = data.sensitivity_presets.find((row) => row.preset_id === "default");
  const sliced = engine.sliceProvinceInput(data.route.engine_input, ["남원시", "순창군"]);
  const actual = engine.calculate(sliced, preset.parameters, data.input_controls);
  assert.equal(actual.covered_target_count, 7);
  assert.deepEqual(actual.coverage_by_tier, { P1: 2, P2: 5 });
  assert.ok(Math.abs(actual.totals.travel_km - 157.905) < 0.001);
  assert.equal(actual.routes.length, 2);
  assert.deepEqual(
    Object.fromEntries(actual.zone_allocations.map((row) => [row.zone_id, row.allocated_route_days])),
    { "남원시": 1, "순창군": 1 },
  );
});


test("two-zone slice stays inside those zones and skips 14-zone fairness", () => {
  const zoneIds = ["남원시", "순창군"];
  for (const zoneId of zoneIds) {
    assert.ok(data.route.engine_input.zones.some((row) => row.zone_id === zoneId));
  }
  const sliced = engine.sliceProvinceInput(data.route.engine_input, zoneIds);
  const allIds = data.route.engine_input.zones.map((row) => row.zone_id);
  const allSliced = engine.sliceProvinceInput(data.route.engine_input, allIds);
  const preset = data.sensitivity_presets.find((row) => row.preset_id === "default");
  const actual = engine.calculate(sliced, preset.parameters, data.input_controls);
  const province = engine.calculate(data.route.engine_input, preset.parameters, data.input_controls);
  assert.equal(sliced.zones.length, 2);
  assert.deepEqual(sliced.zones.map((row) => row.zone_id).sort(), [...zoneIds].sort());
  assert.equal(allSliced, data.route.engine_input);
  assert.equal(actual.target_count, sliced.zones.reduce((sum, zone) => sum + zone.engine_input.targets.length, 0));
  assert.equal(actual.zone_allocations.length, 2);
  assert.ok(actual.zone_allocations.every((row) => zoneIds.includes(row.zone_id)));
  assert.ok(actual.routes.every((route) => zoneIds.includes(route.service_zone)));
  assert.ok(actual.routes.every((route) => route.service_zone !== "정읍시"));
  assert.ok(actual.target_count < province.target_count);
  assert.equal(province.zone_allocations.length, 14);
});


test("one-zone calculate stays inside that zone and skips 14-zone fairness", () => {
  const zone = data.route.engine_input.zones.find((row) => row.zone_id === "정읍시");
  const sliced = engine.sliceProvinceInput(data.route.engine_input, "정읍시");
  const preset = data.sensitivity_presets.find((row) => row.preset_id === "default");
  const actual = engine.calculate(sliced, preset.parameters, data.input_controls);
  const province = engine.calculate(data.route.engine_input, preset.parameters, data.input_controls);
  assert.equal(sliced.zones.length, 1);
  assert.equal(actual.target_count, zone.engine_input.targets.length);
  assert.ok(actual.covered_target_count <= actual.target_count);
  assert.equal(actual.zone_allocations.length, 1);
  assert.equal(actual.zone_allocations[0].zone_id, "정읍시");
  assert.ok(actual.routes.every((route) => route.service_zone === "정읍시"));
  assert.equal(actual.minimum_route_days_per_active_zone, 1);
  assert.equal(province.target_count, 54);
  assert.equal(province.zone_allocations.length, 14);
});


test("shorter service time cannot reduce optimized coverage", () => {
  const base = data.sensitivity_presets.find((row) => row.preset_id === "default").parameters;
  const shortService = engine.calculate(
    data.route.engine_input,
    { ...base, service_minutes: 30 },
    data.input_controls,
  );
  const longService = engine.calculate(
    data.route.engine_input,
    { ...base, service_minutes: 60 },
    data.input_controls,
  );
  assert.ok(shortService.covered_target_count >= longService.covered_target_count);
});

for (const cap of [3, 4, 5]) {
  test(`all three browser methods match frozen report experiment at cap ${cap}`, () => {
    const comparison = engine.compare(data.route.engine_input,
      { ...data.report_evidence.reference_parameters, max_stops_per_route: cap }, data.input_controls);
    assert.deepEqual(comparison.zone_allocation, data.report_evidence.reference_allocation);
    for (const [method, actual] of Object.entries(comparison.results)) {
      const expected = data.report_evidence.cap_sensitivity.find((row) => row.cap === cap && row.method === method);
      assert.deepEqual(actual.coverage_by_tier, expected.coverage);
      assert.equal(actual.covered_target_count, expected.covered);
      assert.equal(actual.totals.travel_km, expected.distance_km);
      assert.equal(actual.totals.max_route_elapsed_minutes, expected.maximum_route_minutes);
      assert.equal(actual.route_days_used, expected.used_days);
      assert.deepEqual(actual.unvisited_targets.map((row) => row.target_id).sort(), expected.unvisited.map((row) => row.target_id).sort());
    }
    if (cap === 4) {
      assert.deepEqual(comparison.results.exact_dp.covered_target_ids, comparison.results.priority_nearest.covered_target_ids);
      assert.notDeepEqual(comparison.results.exact_dp.covered_target_ids, comparison.results.nearest.covered_target_ids);
    }
  });
}

test("timeline independently replays raw matrix legs, windows, return and target complement", () => {
  const plan = engine.calculate(data.route.engine_input, data.report_evidence.reference_parameters, data.input_controls);
  const seen = new Set();
  let distance = 0;
  for (const route of plan.routes) {
    const zone = data.route.engine_input.zones.find((row) => row.zone_id === route.service_zone).engine_input;
    let current = engine.parseHHMM(plan.parameters.operating_start);
    let previous = zone.start_node_id;
    let routeDistance = 0;
    assert.deepEqual(route.timeline.map((row) => row.candidate_id), route.stops);
    for (const stop of route.timeline) {
      const candidate = zone.candidates.find((row) => row.candidate_id === stop.candidate_id);
      const arrival = current + zone.travel_minutes[previous][stop.candidate_id];
      current = Math.max(arrival, engine.parseHHMM(candidate.time_window_start)) + plan.parameters.service_minutes;
      assert.ok(Math.abs(stop.arrival_minute - arrival) < 0.000001);
      assert.ok(Math.abs(stop.service_end_minute - current) < 0.000001);
      assert.ok(current <= engine.parseHHMM(candidate.time_window_end));
      assert.equal(stop.travel_minutes_from_previous, zone.travel_minutes[previous][stop.candidate_id]);
      routeDistance += zone.distance_km[previous][stop.candidate_id];
      for (const target of candidate.serves_target_ids) { assert.ok(!seen.has(target)); seen.add(target); }
      previous = stop.candidate_id;
    }
    assert.equal(route.return_leg.travel_minutes, zone.travel_minutes[previous][zone.end_node_id]);
    current += route.return_leg.travel_minutes;
    assert.ok(current <= engine.parseHHMM(plan.parameters.operating_end));
    routeDistance += zone.distance_km[previous][zone.end_node_id];
    assert.ok(Math.abs(routeDistance - route.travel_km) <= 0.00051);
    distance += route.travel_km;
  }
  assert.ok(Math.abs(distance - plan.totals.travel_km) < 0.001);
  assert.deepEqual([...seen].sort(), plan.covered_target_ids);
  const all = data.route.engine_input.zones.flatMap((zone) => zone.engine_input.targets.map((target) => target.target_id));
  assert.deepEqual(plan.unvisited_targets.map((row) => row.target_id).sort(), all.filter((id) => !seen.has(id)).sort());
  assert.equal(plan.unvisited_targets.length, 4);
  assert.ok(plan.unvisited_targets.every((row) => row.reason === "not_selected_under_stop_time_objective"));
});

test("fixed reference comparison handles empty scope and distinguishes allocation optimization", () => {
  const params = data.report_evidence.reference_parameters;
  const empty = engine.compare(engine.sliceProvinceInput(data.route.engine_input, []), params, data.input_controls);
  assert.ok(Object.values(empty.results).every((plan) => plan.target_count === 0 && plan.routes.length === 0));
  const fixed = engine.compare(data.route.engine_input, { ...params, max_stops_per_route: 3 }, data.input_controls);
  const joint = engine.calculate(data.route.engine_input, { ...params, max_stops_per_route: 3 }, data.input_controls);
  assert.equal(fixed.results.exact_dp.totals.travel_km, 917.731);
  assert.equal(joint.totals.travel_km, 912.448);
  assert.equal(joint.allocation_method, "priority_dp");
});

test("sufficient day capacity cannot overcome closed venue windows", () => {
  const plan = engine.calculate(data.route.engine_input,
    { ...data.report_evidence.reference_parameters, operating_start: "06:00", operating_end: "07:00" }, data.input_controls);
  assert.equal(plan.route_day_capacity, 15);
  assert.equal(plan.routes.length, 0);
  assert.equal(plan.unvisited_targets.length, 54);
  assert.equal(plan.all_zones_allocated, false);
  assert.ok(plan.zone_allocations.every((zone) => zone.allocated_route_days === 0));
});
