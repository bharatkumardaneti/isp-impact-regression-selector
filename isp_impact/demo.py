import copy
import csv
import json
from pathlib import Path
import random
from .demo_adapter import write_pgm


def generate(output):
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    (root / 'images').mkdir()
    rng = random.Random(27)
    rows = []
    for i in range(48):
        gain = [1, 2, 3, 4, 6, 8, 12, 16, 20, 24, 28, 32][i % 12]
        pixels = [max(0, min(255, (50 if x < 16 else 190) + rng.randint(-25,25))) for y in range(32) for x in range(32)]
        filename = f'images/frame_{i:03}.pgm'
        write_pgm(root / filename, 32, 32, pixels)
        rows.append({'id': f'frame_{i:03}', 'path': filename, 'kind': 'sequence' if i >= 36 else 'still',
                     'sequence_id': f'seq_{(i-36)//4}' if i >= 36 else '', 'frame_index': str((i-36)%4) if i >= 36 else '',
                     'sensor': 'demo', 'pipeline': 'grayscale', 'scenario': 'default',
                     'gain': '' if i == 0 else str(gain), 'processing_gain': str(gain)})
    with (root / 'catalog.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    before = {'schema_version': 1, 'execution_contract': {'pipeline': 'demo-v1', 'trigger': 'gain', 'interpolation': 'linear-support-4-24'},
              'modules': {'DENOISE': {'regions': {'HIGH': {'parameters': {'strength': .2}}}}}}
    after = copy.deepcopy(before)
    after['modules']['DENOISE']['regions']['HIGH']['parameters']['strength'] = .8
    rules = {'modules': {'DENOISE': {'locality_verified': True, 'support_verified': True,
                                   'regions': {'HIGH': {'support': [{'gain': [4,24]}]}}}}}
    adapter = {'argv': ['{python}', '-m', 'isp_impact.demo_adapter', '{job}']}
    for filename, obj in [('baseline.json',before), ('candidate.json',after), ('rules.json',rules), ('adapter.json',adapter)]:
        (root / filename).write_text(json.dumps(obj, indent=2), encoding='utf-8')
    return root
