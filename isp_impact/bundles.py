"""Diff a public normalized tuning format; vendor parsing belongs in adapters."""
from .selection import digest


def validate_bundle(bundle):
    if not isinstance(bundle, dict) or bundle.get('schema_version') != 1:
        raise ValueError('Tuning schema_version must be 1')
    if set(bundle) != {'schema_version', 'execution_contract', 'modules'}:
        raise ValueError('Unexpected or missing tuning bundle fields')
    if not isinstance(bundle['execution_contract'], dict) or not bundle['execution_contract']:
        raise ValueError('execution_contract must be a nonempty object')
    if not isinstance(bundle['modules'], dict) or not bundle['modules']:
        raise ValueError('modules must be a nonempty object')
    for name, module in bundle['modules'].items():
        if not name or not isinstance(module, dict) or set(module) != {'regions'}:
            raise ValueError('Each module must contain only regions')
        if not isinstance(module['regions'], dict) or not module['regions']:
            raise ValueError('regions must be nonempty')
        for region in module['regions'].values():
            if not isinstance(region, dict) or set(region) != {'parameters'} or not isinstance(region['parameters'], dict):
                raise ValueError('Each region must contain a parameters object')


def tuning_diff(before, after):
    validate_bundle(before)
    validate_bundle(after)
    structural = before['execution_contract'] != after['execution_contract']
    structural |= set(before['modules']) != set(after['modules'])
    changes = []
    for name in sorted(set(before['modules']) | set(after['modules'])):
        old = before['modules'].get(name, {}).get('regions', {})
        new = after['modules'].get(name, {}).get('regions', {})
        if set(old) != set(new):
            structural = True
        regions = [r for r in sorted(set(old) | set(new)) if old.get(r) != new.get(r)]
        if regions:
            changes.append({'module': name, 'kind': 'parameter_values', 'regions': regions})
    # Always conservative across scopes: normalized bundle applies to whole catalog.
    if structural:
        changes = [{'module': name, 'kind': 'structural'} for name in sorted(set(before['modules']) | set(after['modules']))]
    return {'schema_version': 1, 'diff_complete': True, 'scope_resolved': True,
            'execution_contract_unchanged': not structural, 'changes': changes,
            'baseline_hash': digest(before), 'candidate_hash': digest(after)}
