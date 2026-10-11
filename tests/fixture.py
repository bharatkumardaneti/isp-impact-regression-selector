"""Generate synthetic metadata and exercise selection. No RAWs or ISP simulated."""
import csv
import json
from pathlib import Path
from isp_impact.selection import plan, write_plan


def fixture():
    rules = {"modules": {"ANR": {
        "locality_verified": True, "support_verified": True,
        "regions": {"R_HIGH": {"support": [{"gain": [6, 20], "cct": [2500, 8000]}]}}
    }}}
    change = {"diff_complete": True, "scope_resolved": True,
              "execution_contract_unchanged": True, "trace_context": "synthetic-baseline-v1",
              "changes": [{"module": "ANR", "kind": "parameter_values", "regions": ["R_HIGH"],
                           "scope": {"sensor": ["SENSOR_A"], "pipeline": ["IPE"], "scenario": ["default"]}}]}
    rows = []
    for i in range(240):
        rows.append({"id": f"still_{i:03}", "path": f"/synthetic/raw/still_{i:03}.raw",
                     "kind": "still", "sensor": "SENSOR_A" if i < 180 else "SENSOR_B",
                     "pipeline": "IPE", "scenario": "default", "gain": str([1, 2, 4, 8, 12, 16, 24, 32][i % 8]),
                     "cct": str([3000, 5000, 9000][i % 3]), "sequence_id": "", "frame_index": "",
                     "trace_context": "", "trace_json": ""})
    rows[0]["gain"] = ""  # Missing metadata must stay in the set.
    for seq in range(6):
        for frame in range(10):
            rows.append({"id": f"seq_{seq}_{frame:02}", "path": f"/synthetic/raw/seq_{seq}/{frame:02}.raw",
                         "kind": "sequence", "sensor": "SENSOR_A", "pipeline": "IPE", "scenario": "default",
                         "gain": str(12 if seq < 2 and frame == 5 else 2), "cct": "5000",
                         "sequence_id": f"seq_{seq}", "frame_index": str(frame), "trace_context": "", "trace_json": ""})
    return rows, change, rules

