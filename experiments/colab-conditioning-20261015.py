"""New conditioning ablation, following confirmed loss of the comparison ZIP.

Execute after verified-source and isolated-setup in the existing saved notebook.
This does not claim to implement trained Re-CatVTON. The default application
continues to use official CatVTON conditioning until visual review supports a change.
"""

import json
import os
import subprocess
from datetime import datetime, timezone

python = PROJECT / '.venv-colab/bin/python'
assert python.is_file(), 'The verified inference environment is unavailable'
marker = PROJECT / 'conditioning-ablation-started.json'
assert not marker.exists(), 'Already submitted: inspect its existing results, do not replay'
RUNS = PROJECT / 'experiments/colab-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RUNS.mkdir(parents=True)
marker.write_text(json.dumps({'runDirectory': str(RUNS), 'experiment': 'conditioning-ablation-v1'}))
environment = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONNOUSERSITE': '1'}
environment.pop('PYTHONPATH', None)
environment.pop('PYTHONHOME', None)
cases = [
    ('stripe-control', 'data/raw/studio-person.jpg', 'data/raw/garment-demo.png', 'official'),
    ('stripe-anchored', 'data/raw/studio-person.jpg', 'data/raw/garment-demo.png', 'reference-anchor'),
    ('different-person-anchored', 'data/raw/vton-official/person-model-5.png',
     'data/raw/vton-official/garment-rhude.jpg', 'reference-anchor'),
]
for name, person, garment, conditioning in cases:
    destination = RUNS / name
    command = [str(python), str(PROJECT / 'scripts/colab_runtime.py'), 'run',
               '--person', str(PROJECT / person), '--garment', str(PROJECT / garment),
               '--output', str(destination), '--checkpoint', 'vitonhd', '--height', '512',
               '--conditioning', conditioning, '--seed', '42', '--guidance', '2.5']
    print('Testing', name, 'with fixed checkpoint, mask, seed and guidance', flush=True)
    with (RUNS / f'{name}.log').open('w') as log:
        completed = subprocess.run(command, cwd=PROJECT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    report_path = destination / 'report.json'
    if not report_path.is_file():
        raise RuntimeError(f'{name} did not produce a report; inspect its subprocess log')
    report = json.loads(report_path.read_text())
    print(json.dumps({key: report.get(key) for key in (
        'status', 'code', 'error', 'seconds', 'checkpoint', 'conditioning',
    )}), flush=True)
