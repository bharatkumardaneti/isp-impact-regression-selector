# Input formats

## Catalog

CSV with one row per frame. Required: `id`, `path`, `kind`. `kind` is `still` or `sequence`. Sequences also require `sequence_id` and nonnegative integer `frame_index`. IDs must be unique; `(sequence_id, frame_index)` pairs must be unique. Keep sequence IDs globally unique within the catalog.

Optional selection metadata: `sensor`, `pipeline`, `scenario`, and numeric trigger columns such as `gain` or `cct`. Missing/nonfinite trigger values conservatively retain potentially affected rows. Unknown scope is also retained. Paths must be local or mounted filesystem paths, not HTTP/S3 URIs. Relative paths resolve against the CSV's directory. The planner reads every input to hash it; it does not decode it.

```csv
id,path,kind,sensor,pipeline,scenario,gain,cct,sequence_id,frame_index
frame-001,images/frame-001.raw,still,sensor-a,ipe,default,8,5000,,
```

Every sequence must include all frames from a known reset/start, including warm-up frames. This release does not distinguish warm-up from scored frames. Completeness of the original sequence cannot be proven from a CSV alone. Do not label temporal inputs as independent stills.

Metadata names and units must match the actual trigger signal. ISO is not automatically interchangeable with analog/total sensor gain. Extract effective runtime trigger values where raw capture metadata is insufficient.

## Normalized tuning bundles (schema version 1)

```json
{
  "schema_version": 1,
  "execution_contract": {
    "pipeline": "demo-v1",
    "trigger": "gain",
    "interpolation": "linear-support-4-24"
  },
  "modules": {
    "DENOISE": {
      "regions": {
        "HIGH": {"parameters": {"strength": 0.2}}
      }
    }
  }
}
```

The candidate has the same structure with modified parameter values. Top-level/module/region unknown fields are rejected so untracked fields cannot silently be ignored. Parameters may be nested JSON; the diff compares entire parameter objects and selects the changed region.

The exporter must put all execution-affecting nonlocal changes in `execution_contract`: trigger thresholds, enable switches, control-method selection, simulator version, interpolation, routing, inherited scenario relationships, and so on. A difference in that object, module set or region set produces full-suite selection. Never misclassify a control/layout change as a local numeric parameter adjustment.

The current CLI applies each normalized bundle across the entire catalog, conservatively. It does not resolve proprietary scenario inheritance or automatically narrow by scope. Build/export separately resolved bundles for your first integration. The underlying selector supports manually described scopes, but this normalized diff CLI does not emit them.

## Influence rules

```json
{
  "modules": {
    "DENOISE": {
      "locality_verified": true,
      "support_verified": true,
      "regions": {
        "HIGH": {"support": [{"gain": [4, 24]}]}
      }
    }
  }
}
```

`locality_verified` asserts the changed values cannot affect executions outside the influence set, including downstream feedback. `support_verified` asserts boxes cover every nonzero region contribution, including interpolation. These flags are supplied engineering attestations, not automatically established facts. Keep them false until verified. A false/missing contract selects broadly.

OR between boxes, AND between axes in a box. Bounds are inclusive; `null` denotes an unbounded end. Include hysteresis, measurement uncertainty and interpolation shoulders conservatively. For demo HIGH the actual weight is `max(0,min(1,(gain-4)/4,(24-gain)/8))`, so [4,24] includes all contributing inputs and harmless endpoints.

Rules unknown to the changed module produce full fallback. Missing/unverified region support retains affected-scope rows. The default 5% canary sample is deterministic per scope/kind stratum, rounded up; complete sequence expansion can increase it substantially. Canary sampling is not a coverage guarantee and currently does not rotate across changes.

The low-level selector retains trace support from the original POC, but the public v0.2 CLI deliberately does not emit a trace context. Consequently CLI plans use the rule path, not unverifiable cached traces. A trustworthy trace exporter is future work.
