# Simulator adapter contract

The adapter is a trusted executable you choose. It receives one job JSON, processes every frame in order, and writes a result JSON mapping each frame ID to an output artifact. There are separate jobs for baseline and candidate, each starting at a reset boundary. Independent jobs can run concurrently; frames within a sequence must not be independently shuffled or reset.

Example `adapter.json`:

```json
{"argv":["{python}","/absolute/path/my_adapter.py","{job}"]}
```

The runner substitutes `{python}` with its Python executable and `{job}` with the job JSON's absolute path. It passes the array directly to subprocess, with no shell. Use absolute adapter/resource paths. Working directory is inherited from the CLI. Adapter arguments are local executable configuration, not untrusted remote submissions.

Job structure:

```json
{
  "schema_version": 1,
  "variant": "baseline",
  "tuning": {"schema_version":1,"execution_contract":{},"modules":{}},
  "reset_state": true,
  "kind": "sequence",
  "frames": [{"id":"f1","path":"/data/f1.raw","frame_index":"0"}],
  "result_path": "/output/job/result.json",
  "output_dir": "/output/job"
}
```

The tuning example above is abbreviated; real jobs include the complete validated bundle. Frames contain all catalog columns, input hashes and selection reasons. Apply the given tuning and run the full desired pipeline, including downstream processing. `reset_state` is an instruction the adapter must honor; the runner cannot inspect hidden simulator state.

After successful processing:

```json
{"artifacts":{"f1":"frame_000000.yuv"}}
```

Return exactly one distinct file per frame. Relative output paths resolve under output_dir; absolute paths must also lie inside it. Symlinks resolving outside it are rejected. Missing artifacts, malformed results, nonzero process exits and timeouts fail the run. stdout/stderr are saved per job.

One artifact per frame is a current simplification. To compare several pipeline outputs, emit a deterministic combined representation. Do not include timestamps or run-specific paths in that representation. Exact SHA-256 comparisons detect any byte difference; they do not compute PSNR, SSIM, Imatest KPIs or task accuracy. Extend the comparator when those acceptance policies are available.

Each job gets fresh output paths, so old results cannot masquerade as successful new output. Input hashes are checked before and after execution. Mount inputs read-only where possible; before/after hashing cannot detect a transient change restored during a run. The plan digest detects accidental mutation, not malicious rewriting/signing.

Timeout applies to the directly launched process. It does not promise to terminate a simulator's independently spawned process tree. Adapters must supervise/clean up children and avoid returning before output is complete. No cancellation/resume, license-aware scheduler, sandbox or container isolation is provided.
