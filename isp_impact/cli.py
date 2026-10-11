import argparse
import json
from pathlib import Path
import sys
from .bundles import tuning_diff
from .selection import load_catalog, plan, write_plan
from .runner import run, validate, file_hash, seal
from .demo import generate


def read(path):
    def invalid(value):
        raise ValueError('Nonfinite JSON number: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=invalid)


def make_plan(catalog, before, after, rules, canaries=.05):
    rows = load_catalog(catalog)
    for row in rows:
        path = Path(row['path'])
        if not path.is_absolute():
            path = Path(catalog).resolve().parent / path
        row['path'] = str(path.resolve())
        row['input_sha256'] = file_hash(path)
    change = tuning_diff(before, after)
    if not change['changes']:
        raise ValueError('No tuning changes; nothing to plan')
    result = plan(rows, change, rules, canaries)
    result.update(schema_version=1, baseline_hash=change['baseline_hash'], candidate_hash=change['candidate_hash'], tuning_diff=change)
    return seal(result)


def emit(obj):
    print(json.dumps(obj, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(prog='isp-impact', description='Select and validate tuning regression datasets')
    sub = parser.add_subparsers(dest='command', required=True)
    d = sub.add_parser('diff', help='Compare normalized tuning bundles')
    for key in ('baseline','candidate'):
        d.add_argument('--'+key, required=True)
    p = sub.add_parser('plan', help='Hash inputs and select regression inputs')
    for key in ('catalog', 'baseline', 'candidate', 'rules', 'out'):
        p.add_argument('--'+key, required=True)
    p.add_argument('--canary-fraction', type=float, default=.05)
    r = sub.add_parser('run', help='Execute trusted adapter for both variants')
    for key in ('plan', 'baseline', 'candidate', 'adapter', 'out'):
        r.add_argument('--'+key, required=True)
    r.add_argument('--mode', choices=['selected','full'], default='selected')
    r.add_argument('--workers', type=int, default=2)
    r.add_argument('--timeout', type=float, default=60)
    v = sub.add_parser('validate', help='Check excluded changed outputs')
    v.add_argument('--plan', required=True)
    v.add_argument('--run', required=True)
    demo = sub.add_parser('demo', help='Generate pixels, plan, run full and selected, validate')
    demo.add_argument('--out', default='demo-workspace')
    args = parser.parse_args(argv)
    try:
        if args.command == 'diff':
            emit(tuning_diff(read(args.baseline), read(args.candidate)))
        elif args.command == 'plan':
            out = Path(args.out)
            if out.exists():
                raise ValueError('Use a new output directory')
            result = make_plan(args.catalog, read(args.baseline), read(args.candidate), read(args.rules), args.canary_fraction)
            write_plan(result, out)
            emit({'plan_id': result['plan_id'], 'summary': result['summary'], 'warnings': result['warnings']})
        elif args.command == 'run':
            result = run(read(args.plan), read(args.baseline), read(args.candidate), read(args.adapter), args.out, args.mode, args.workers, args.timeout)
            emit({'success': result['success'], 'jobs': result['jobs'], 'errors': result['errors'], 'wall_seconds': result['wall_seconds']})
            return 0 if result['success'] else 2
        elif args.command == 'validate':
            result = validate(read(args.plan), read(args.run))
            emit(result)
            return 0 if result['passed'] else 2
        else:
            root = generate(args.out)
            before, after, rules, adapter = [read(root / name) for name in ('baseline.json','candidate.json','rules.json','adapter.json')]
            result = make_plan(root / 'catalog.csv', before, after, rules)
            write_plan(result, root / 'plan')
            full = run(result, before, after, adapter, root / 'full', 'full')
            if not full['success']:
                emit(full)
                return 2
            selected = run(result, before, after, adapter, root / 'selected')
            validation = validate(result, full)
            summary = {'selection': result['summary'], 'validation': validation, 'selected_run_success': selected['success'],
                       'full_jobs': full['jobs'], 'selected_jobs': selected['jobs'],
                       'note': 'Actual synthetic PGM pixels processed. Educational denoiser, not a real ISP or quality benchmark.'}
            (root / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
            emit(summary)
            return 0 if validation['passed'] and selected['success'] else 2
        return 0
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        print('Error: '+str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
