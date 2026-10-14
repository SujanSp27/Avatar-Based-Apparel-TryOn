"""Notebook continuation after the current verified-source and setup cells.

Two new diagnostic cases use the installed vitonhd checkpoint at its 384x512
resolution, with the rounded shoulder-cap mask. This is not a controlled ablation
of either change independently, and is not training. Retain the previous run.
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# The old runtime's files were lost, but its completed archive was recovered
# locally and verified before authorizing this comparison. No old case is replayed.
recovered_archive_sha256 = '030a79942c9488ed5fe1c6caf59c6ad991374604b5ec20f127067a7346ba59bc'
python = PROJECT / '.venv-colab/bin/python'
assert python.is_file(), 'The verified inference environment is unavailable'
marker = PROJECT / 'comparison-started.json'
assert not marker.exists(), 'Already submitted: inspect the existing reports, do not rerun'
RUNS = PROJECT / 'experiments/colab-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RUNS.mkdir(parents=True)
marker.write_text(json.dumps({'runDirectory': str(RUNS), 'checkpoint': 'vitonhd-16k-512',
                             'previousRecoveredArchiveSha256': recovered_archive_sha256}))
environment = {**os.environ, 'MPLBACKEND': 'Agg', 'PYTHONNOUSERSITE': '1'}
environment.pop('PYTHONPATH', None)
environment.pop('PYTHONHOME', None)
cases = [
    ('reported-striped-shirt', 'data/raw/studio-person.jpg', 'data/raw/garment-demo.png'),
    ('different-person', 'data/raw/vton-official/person-model-5.png', 'data/raw/vton-official/garment-rhude.jpg'),
]
for name, person, garment in cases:
    destination = RUNS / name
    command = [str(python), str(PROJECT / 'scripts/colab_runtime.py'), 'run',
               '--person', str(PROJECT / person), '--garment', str(PROJECT / garment),
               '--output', str(destination), '--checkpoint', 'vitonhd', '--height', '512']
    print('Testing', name, 'with vitonhd-16k-512 and rounded shoulder caps', flush=True)
    with (RUNS / f'{name}.log').open('w') as log:
        finished = subprocess.run(command, cwd=PROJECT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    report = json.loads((destination / 'report.json').read_text())
    print(json.dumps({key: report.get(key) for key in ('status', 'code', 'error', 'seconds', 'checkpoint')}), flush=True)
