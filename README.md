# ISP Impact

**Select regression inputs from a tuning change, execute both tuning versions, and check selection against a full run.**

ISP Impact is an early, working Python practice project for camera tooling engineers. It has no third-party runtime dependencies. It runs locally and can invoke your existing simulator through a small adapter. The included demo actually processes generated images and compares output hashes.

It is not a validated production ISP regression system. Its selection is only as sound as the supplied region-influence and locality contracts. A full-run comparison detects missed changed outputs for that run; it does not establish image-quality acceptance or guarantee future coverage.

## Try it on macOS

Python 3.10 or newer. From the extracted repository folder:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
isp-impact demo --out demo-workspace
python -m unittest discover -s tests -v
```

No installation is needed to try it directly from source:

```sh
python3 -m isp_impact demo --out demo-workspace
```

Use a new output folder for every run; existing folders are not overwritten. Do not run the two demo commands above with the same output folder. Windows users can run `.venv\Scripts\activate` and use `python` in place of `python3`.

Verified locally on Python 3.12/Linux: **28 tests pass**. macOS and Windows compatibility is intended through standard-library APIs, but those platforms have not been executed in this development environment. GitLab CI is configured for Python 3.10, 3.12 and 3.13; that hosted pipeline has not yet run.

### What the demo does

1. Creates 48 small grayscale PGM images with noisy edges.
2. Changes one denoising strength from 0.2 to 0.8.
3. Diffs the tuning bundles and selects 35 frames, including sequence expansion and canaries.
4. Executes full baseline/candidate processing: 78 process jobs.
5. Executes selected baseline/candidate processing: 52 process jobs.
6. Checks all 20 observed changed outputs were selected: zero missed changes in this demo.

These numbers describe a deterministic educational example, not expected savings on customer data. Process startup dominates this small example. The demo filter is a spatial 3x3 average blended with the original; it is not a bit-exact hardware ISP, Bayer pipeline, temporal denoiser or quality benchmark.

Output locations:

| File | Purpose |
|---|---|
| `demo-workspace/summary.json` | Selection and full-run validation results |
| `demo-workspace/plan/selected.csv` | Selected frames, paths and reasons |
| `demo-workspace/plan/decisions.csv` | Both included and excluded frames |
| `demo-workspace/plan/plan.json` | Bound execution plan and fingerprints |
| `demo-workspace/full/run.json` | Full baseline/candidate comparison |
| `demo-workspace/selected/run.json` | Selected-run results |
| `demo-workspace/full/job_*/frame_*.pgm` | Actual processed output images |

## Features

- Normalized JSON tuning diff: changed module and region IDs.
- Conservative trigger-support matching across multiple axes, including interpolation support.
- Unknown metadata/support fallback; full selection for structural execution-contract changes.
- Deterministic canaries and complete sequence replay.
- Local CSV paths resolved relative to the catalog, with SHA-256 input checks.
- Parallel process jobs for independent stills/sequences, bounded worker count and per-process timeout.
- No shell interpolation of adapter arguments.
- Per-job logs, failure reports, and exact output-byte comparisons.
- Full-run validation bound to plan and input fingerprints.

## Use your own data

See [data formats](docs/FORMATS.md) and the [adapter contract](docs/ADAPTERS.md). A public normalized format deliberately avoids proprietary tuning schemas. Export your tuning bundles into that format; an XML/schema-specific exporter is not included.

```sh
isp-impact diff --baseline baseline.json --candidate candidate.json
isp-impact plan --catalog catalog.csv --baseline baseline.json --candidate candidate.json --rules rules.json --out plan-001
isp-impact run --plan plan-001/plan.json --baseline baseline.json --candidate candidate.json --adapter adapter.json --out full-001 --mode full --workers 4 --timeout 300
isp-impact validate --plan plan-001/plan.json --run full-001/run.json
isp-impact run --plan plan-001/plan.json --baseline baseline.json --candidate candidate.json --adapter adapter.json --out selected-001 --mode selected --workers 4 --timeout 300
```

Initially run in shadow mode: use full regression while evaluating the proposed subset. Retain periodic full runs after adoption. A mismatch should disable pruning until the contract is repaired. Validation reports a failure; it does not automatically change your CI policy.

Exit codes: 0 success; 1 invalid input/configuration; 2 simulator execution failure or observed selection miss. A no-op tuning change yields exit 1 with “No tuning changes”; it is not silently interpreted as a useful validation run.

## Architecture and practice path

The workflow is `tuning diff -> selection plan -> baseline/candidate runner -> full-run validation`.

| Component | Responsibility |
|---|---|
| `bundles.py` | Validate and diff normalized tuning bundles |
| `selection.py` | Match influence ranges; retain uncertainty and sequences |
| `runner.py` | Execute adapters; fingerprint artifacts; validate observations |
| `demo_adapter.py` | Reference adapter with real pixel processing |
| `cli.py` | Commands and error handling |

Learn by making one change at a time:

1. Run the demo and explain why each selected frame was retained.
2. Change candidate strength and rerun into a fresh directory.
3. Narrow the support incorrectly to [10,14]; observe full validation catch missed changes.
4. Add a second trigger axis and test its boundaries.
5. Implement a local simulator adapter and run a small authorized dataset.
6. Extend comparison to agreed IQ metrics; keep exact output differences as separate evidence.

See [limitations](docs/LIMITATIONS.md) before integrating a real pipeline.

## Publish to GitLab

Create an empty GitLab project named `isp-impact` without a generated README. In this directory:

```sh
git init -b main
git add .
git commit -m "Initial ISP Impact implementation"
git remote add origin YOUR_GITLAB_REPOSITORY_URL
git push -u origin main
```

Replace `YOUR_GITLAB_REPOSITORY_URL` with the SSH or HTTPS URL GitLab gives you. No repository has been created or pushed by this deliverable. Set project visibility to Public if you want public access. The provided `.gitlab-ci.yml` runs tests, the end-to-end demo and builds a wheel.

MIT licensed. Contributions welcome; see [CONTRIBUTING.md](CONTRIBUTING.md).
