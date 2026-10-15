import os, json, subprocess
from pathlib import Path
from datetime import datetime, timezone
previous = Path('/content/avatar-vton-38a9b75373f4')
python = previous / '.venv-colab/bin/python'
assert python.is_file(), 'Reuse the existing verified environment; do not reinstall silently'
assert (previous / 'assets/vton').is_dir(), 'Existing model weights unavailable'
assert not (PROJECT / 'confirmation-started.json').exists(), 'Already submitted; do not rerun'
(PROJECT / 'assets').symlink_to(previous / 'assets', target_is_directory=True)
RUNS = PROJECT / 'experiments/colab-runs' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
RUNS.mkdir(parents=True)
(PROJECT / 'confirmation-started.json').write_text(json.dumps({'runDirectory':str(RUNS)}))
environment = {**os.environ, 'MPLBACKEND':'Agg','PYTHONNOUSERSITE':'1'}
environment.pop('PYTHONPATH',None); environment.pop('PYTHONHOME',None)
for name, garment, category in [('different-garment','garment-number-95.jpg','t-shirt'),('shirt-category','garment-rhude.jpg','shirt')]:
    command=[str(python),str(PROJECT/'scripts/colab_runtime.py'),'run','--person',str(PROJECT/'data/raw/studio-person.jpg'),'--garment',str(PROJECT/'data/raw/vton-official'/garment),'--category',category,'--output',str(RUNS/name),'--checkpoint','vitonhd','--height','512','--conditioning','reference-anchor']
    print('Testing',name,flush=True)
    with (RUNS/f'{name}.log').open('w') as log:
        subprocess.run(command,cwd=PROJECT,env=environment,stdout=log,stderr=subprocess.STDOUT)
    record=json.loads((RUNS/name/'report.json').read_text())
    print(json.dumps({k:record.get(k) for k in ('status','code','error','seconds','checkpoint','conditioning')}),flush=True)
