#!/usr/bin/env python3
"""Auditable ISP regression selection. Python 3.10+, standard library only."""
import csv
import hashlib
import json
import math
from pathlib import Path

VERSION = "0.2.0"
SCOPE = ("sensor", "pipeline", "scenario")


def number(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_catalog(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError("Empty catalog")
    ids = [r.get("id") for r in rows]
    if not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Catalog IDs must be nonempty and unique")
    for row in rows:
        if not row.get("path"):
            raise ValueError("Each catalog row requires path")
        if row.get("kind") not in ("still", "sequence"):
            raise ValueError("kind must be still or sequence; do not label temporal inputs as still")
        if row["kind"] == "sequence":
            idx = number(row.get("frame_index"))
            if not row.get("sequence_id") or idx is None or idx < 0 or not idx.is_integer():
                raise ValueError("Sequence rows require sequence_id and nonnegative integer frame_index")
    pairs = [(r["sequence_id"], int(r["frame_index"])) for r in rows if r["kind"] == "sequence"]
    if len(pairs) != len(set(pairs)):
        raise ValueError("Duplicate frame index in sequence")
    return rows


def scope_match(row, scope):
    """Only a known mismatch permits exclusion; missing scope is uncertain."""
    unknown = False
    for key, expected in scope.items():
        if key not in SCOPE or not isinstance(expected, list) or not expected or not all(isinstance(x, str) and x for x in expected):
            raise ValueError("Scope supports nonempty sensor/pipeline/scenario string lists only")
        if not row.get(key):
            unknown = True
        elif row[key] not in expected:
            return False, False
    return True, unknown


def valid_support(region):
    boxes = region.get("support") if isinstance(region, dict) else None
    if not isinstance(boxes, list) or not boxes:
        return False
    for box in boxes:
        if not isinstance(box, dict) or not box:
            return False
        for bounds in box.values():
            if not isinstance(bounds, list) or len(bounds) != 2:
                return False
            lo, hi = bounds
            if any(x is not None and number(x) is None for x in bounds):
                return False
            if lo is not None and hi is not None and float(lo) > float(hi):
                return False
    return True


def support_match(row, region):
    # OR between boxes, AND between axes. Closed bounds intentionally retain boundaries.
    uncertain = False
    for box in region["support"]:
        outside, missing = False, False
        for axis, (lo, hi) in box.items():
            value = number(row.get(axis))
            if value is None:
                missing = True
            elif (lo is not None and value < float(lo)) or (hi is not None and value > float(hi)):
                outside = True
        if not outside:
            if not missing:
                return True, False
            uncertain = True
    return uncertain, uncertain


def active_trace(row, module, context):
    # Exporter asserts this is the COMPLETE set of regions with nonzero contribution.
    # Context binds input metadata, tuning schema, simulator, routing and baseline bundle.
    if not context or row.get("trace_context") != context:
        return None
    try:
        trace = json.loads(row.get("trace_json", ""))[module]
        active = trace["active_regions"]
        if trace.get("complete") is not True or not isinstance(active, list) or not all(isinstance(x, str) for x in active):
            return None
        return set(active)
    except (ValueError, KeyError, TypeError):
        return None


def plan(rows, change, rules, canary_fraction=0.05):
    if not 0 <= canary_fraction <= 1:
        raise ValueError("canary_fraction must be in [0, 1]")
    if not isinstance(change.get("changes"), list) or not change["changes"]:
        raise ValueError("A nonempty changes list is required")
    reasons = {r["id"]: set() for r in rows}
    # No partial/ambiguous diff is allowed to narrow scope.
    global_fallback = None
    if change.get("diff_complete") is not True:
        global_fallback = "full_suite:diff_not_complete"
    if change.get("scope_resolved") is not True:
        global_fallback = "full_suite:scenario_inheritance_not_resolved"
    if change.get("execution_contract_unchanged") is not True:
        global_fallback = "full_suite:execution_contract_changed_or_unknown"
    # Metadata gates and cached traces cannot safely model cascading routing/control changes.
    if any(c.get("kind") != "parameter_values" for c in change["changes"]):
        global_fallback = "full_suite:structural_or_trigger_change"
    modules = rules.get("modules", {})
    if any(c.get("module") not in modules for c in change["changes"]):
        global_fallback = "full_suite:unknown_module"
    warnings = []
    if global_fallback:
        for rs in reasons.values():
            rs.add(global_fallback)
        warnings.append(global_fallback)
    else:
        for c in change["changes"]:
            name = c["module"]
            module = modules[name]
            scope = c.get("scope", {})
            scope_match({}, scope)  # Validate even if no row is eligible.
            regions = c.get("regions")
            fallback = None
            if not isinstance(regions, list) or not regions or not all(isinstance(x, str) for x in regions):
                fallback = "module_wide_change"
            elif any(x not in module.get("regions", {}) for x in regions):
                fallback = "unknown_region"
            if module.get("locality_verified") is not True:
                fallback = "locality_unverified"
            if fallback:
                warnings.append(name + ":" + fallback)
            for row in rows:
                eligible, missing_scope = scope_match(row, scope)
                if not eligible:
                    continue
                rs = reasons[row["id"]]
                if missing_scope:
                    rs.add(name + ":unknown_scope")
                elif fallback:
                    rs.add(name + ":" + fallback)
                else:
                    trace = active_trace(row, name, change.get("trace_context"))
                    if trace is not None:
                        hits = trace.intersection(regions)
                        if hits:
                            rs.add(name + ":trace:" + ",".join(sorted(hits)))
                        continue
                    for region_id in regions:
                        region = module["regions"][region_id]
                        if module.get("support_verified") is not True or not valid_support(region):
                            rs.add(name + ":unknown_support:" + region_id)
                        else:
                            hit, unknown = support_match(row, region)
                            if hit:
                                rs.add(name + (":unknown_trigger:" if unknown else ":support:") + region_id)
    direct = {i for i, rs in reasons.items() if rs}
    # Fixed, deterministic canaries per sensor/pipeline/scenario/kind stratum.
    groups = {}
    for row in rows:
        if not reasons[row["id"]]:
            key = tuple(row.get(k, "") for k in (*SCOPE, "kind"))
            groups.setdefault(key, []).append(row)
    for group in groups.values():
        n = math.ceil(len(group) * canary_fraction)
        for row in sorted(group, key=lambda r: digest(r["id"]))[:n]:
            reasons[row["id"]].add("canary")
    selected_sequences = {r["sequence_id"] for r in rows if r["kind"] == "sequence" and reasons[r["id"]]}
    for row in rows:
        if row["kind"] == "sequence" and row["sequence_id"] in selected_sequences:
            reasons[row["id"]].add("sequence_closure:" + row["sequence_id"])
    ordered = sorted(rows, key=lambda r: (r.get("sequence_id") or r["id"], int(r["frame_index"]) if r["kind"] == "sequence" else 0))
    decisions = [{**r, "selected": bool(reasons[r["id"]]), "reasons": sorted(reasons[r["id"]])} for r in ordered]
    selected = [r for r in decisions if r["selected"]]
    return {
        "selector_version": VERSION,
        "fingerprints": {"catalog": digest(rows), "change": digest(change), "rules": digest(rules)},
        "summary": {"total": len(rows), "direct": len(direct), "selected": len(selected),
                    "excluded": len(rows) - len(selected), "frame_reduction_pct": round(100 * (1 - len(selected) / len(rows)), 2),
                    "selected_sequences": len(selected_sequences)},
        "warnings": sorted(set(warnings)), "canary_fraction": canary_fraction,
        "execution": "Run all selected frames through the complete baseline and candidate pipelines. Reset at each sequence boundary; replay every frame in order from sequence start.",
        "decisions": decisions,
    }


def write_plan(result, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "plan.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    rows = result["decisions"]
    fields = list(dict.fromkeys(k for r in rows for k in r))
    for filename, chosen in [("selected.csv", [r for r in rows if r["selected"]]), ("decisions.csv", rows)]:
        with (out / filename).open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in chosen:
                writer.writerow({**row, "reasons": ";".join(row["reasons"])})


def validate_shadow(result, observations):
    """Require full-suite observations; changed is baseline/candidate comparison, not pass/fail."""
    decisions = {r["id"]: r for r in result["decisions"]}
    seen, changed = set(), set()
    for obs in observations:
        i = obs.get("id")
        if i in seen or i not in decisions or obs.get("changed") not in ("0", "1"):
            raise ValueError("Shadow observations require unique known IDs and changed=0/1")
        seen.add(i)
        if obs["changed"] == "1":
            changed.add(i)
    if seen != set(decisions):
        raise ValueError("Shadow validation requires observations for EVERY catalog row")
    missed = sorted(i for i in changed if not decisions[i]["selected"])
    return {"observed_changed": len(changed), "missed_changed": missed,
            "observed_recall": (len(changed) - len(missed)) / len(changed) if changed else None,
            "passed": not missed,
            "note": "One full-run observation, not a guarantee for future changes; zero changed frames provides no recall evidence."}


