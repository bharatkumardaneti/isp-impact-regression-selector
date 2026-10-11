"""One external process per still/sequence and tuning variant; no shell evaluation."""
import concurrent.futures
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time
from .selection import digest


def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def seal(result):
    result['plan_id'] = digest({k: v for k, v in result.items() if k != 'plan_id'})
    return result


def verify_plan(result):
    if result.get('plan_id') != digest({k: v for k, v in result.items() if k != 'plan_id'}):
        raise ValueError('Plan integrity check failed')


def run(result, before, after, adapter, output, mode='selected', workers=2, timeout=60):
    verify_plan(result)
    if mode not in ('selected', 'full') or workers < 1 or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Invalid mode, workers or timeout')
    if digest(before) != result['baseline_hash'] or digest(after) != result['candidate_hash']:
        raise ValueError('Tuning files do not match plan')
    argv = adapter.get('argv') if isinstance(adapter, dict) else None
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        raise ValueError('adapter.argv must be a nonempty string array')
    if not any('{job}' in x for x in argv):
        raise ValueError('adapter.argv must include {job}')
    # Preflight every requested input; never treat missing inputs as unchanged.
    rows = [r for r in result['decisions'] if mode == 'full' or r['selected']]
    inputs = {}
    groups = {}
    for row in rows:
        if file_hash(row['path']) != row['input_sha256']:
            raise ValueError('Input changed since planning: ' + row['id'])
        inputs[row['id']] = row['input_sha256']
        key = ('sequence', row['sequence_id']) if row['kind'] == 'sequence' else ('still', row['id'])
        groups.setdefault(key, []).append(row)
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    tasks = []
    for i, (key, frames) in enumerate(sorted(groups.items())):
        frames = sorted(frames, key=lambda r: int(r['frame_index']) if r['kind'] == 'sequence' else 0)
        for variant, tuning in [('baseline', before), ('candidate', after)]:
            job_dir = out / f'job_{i:06}_{variant}'
            job_dir.mkdir()
            job = {'schema_version': 1, 'variant': variant, 'tuning': tuning,
                   'reset_state': True, 'kind': key[0], 'frames': frames,
                   'result_path': str(job_dir / 'result.json'), 'output_dir': str(job_dir)}
            job_path = job_dir / 'job.json'
            job_path.write_text(json.dumps(job, indent=2), encoding='utf-8')
            tasks.append((job, job_path, job_dir))

    def execute(task):
        job, path, directory = task
        command = [x.replace('{python}', sys.executable).replace('{job}', str(path)) for x in argv]
        started = time.monotonic()
        try:
            with (directory / 'stdout.log').open('wb') as stdout, (directory / 'stderr.log').open('wb') as stderr:
                subprocess.run(command, shell=False, check=True, stdout=stdout, stderr=stderr, timeout=timeout)
            payload = json.loads(Path(job['result_path']).read_text(encoding='utf-8'))
            artifacts = payload['artifacts']
            expected = {r['id'] for r in job['frames']}
            if not isinstance(artifacts, dict) or set(artifacts) != expected:
                raise ValueError('Adapter must return exactly one artifact per job frame')
            hashes = {}
            resolved = set()
            for ident, filename in artifacts.items():
                artifact = Path(filename)
                if not artifact.is_absolute():
                    artifact = directory / artifact
                artifact = artifact.resolve()
                if not artifact.is_relative_to(directory) or artifact in resolved:
                    raise ValueError('Artifacts must be distinct files within job output_dir')
                resolved.add(artifact)
                hashes[ident] = file_hash(artifact)
            return {'variant': job['variant'], 'hashes': hashes, 'elapsed_seconds': time.monotonic() - started}
        except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
            return {'variant': job['variant'], 'job': str(path), 'error': str(exc)}

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        completed = list(pool.map(execute, tasks))
    errors = [r for r in completed if 'error' in r]
    for row in rows:
        if file_hash(row['path']) != row['input_sha256']:
            errors.append({'error': 'Input changed during execution: ' + row['id']})
    hashes = {'baseline': {}, 'candidate': {}}
    for job in completed:
        if 'hashes' in job:
            hashes[job['variant']].update(job['hashes'])
    observations = []
    if not errors:
        observations = [{'id': r['id'], 'changed': hashes['baseline'][r['id']] != hashes['candidate'][r['id']],
                         'baseline_sha256': hashes['baseline'][r['id']], 'candidate_sha256': hashes['candidate'][r['id']]} for r in rows]
    report = {'schema_version': 1, 'plan_id': result['plan_id'], 'mode': mode,
              'adapter_hash': digest(adapter), 'inputs': inputs, 'success': not errors,
              'wall_seconds': time.monotonic() - started, 'jobs': len(tasks),
              'errors': errors, 'observations': observations}
    (out / 'run.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    return report


def validate(result, report):
    verify_plan(result)
    if report.get('plan_id') != result['plan_id'] or report.get('mode') != 'full' or report.get('success') is not True:
        raise ValueError('Validation requires a successful full run bound to this plan')
    decisions = {r['id']: r for r in result['decisions']}
    if report.get('inputs') != {i: r['input_sha256'] for i, r in decisions.items()}:
        raise ValueError('Full run input fingerprints differ from plan')
    observations = report.get('observations', [])
    if len(observations) != len(decisions) or {r['id'] for r in observations} != set(decisions):
        raise ValueError('Full observations required exactly once per frame')
    if any(type(r.get('changed')) is not bool for r in observations):
        raise ValueError('changed must be a boolean')
    changed = [r['id'] for r in observations if r['changed']]
    missed = sorted(i for i in changed if not decisions[i]['selected'])
    return {'passed': not missed, 'changed_frames': len(changed), 'missed_changed': missed,
            'observed_recall': (len(changed) - len(missed)) / len(changed) if changed else None,
            'scope': 'Empirical result for this full run; not proof of future coverage or image quality.'}
