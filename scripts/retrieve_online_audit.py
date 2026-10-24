"""Recover actual conditioning and output artifacts from the pinned Colab.

Never starts inference. Older runs may lack the newer audit files; report their
absence rather than creating substitutes. Files stay within the supplied local
experiment directory and the worker's recorded remote run directory.
"""
import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.deploy_online_colab import call

NAMES = ['raw.png', 'source-labels.png', 'target-labels.png', 'garment-labels.png',
         'edit-mask.png', 'result.png', 'report.json', 'inputs.json', 'conditioning.json',
         'person-input.png', 'garment-input.png', 'person-conditioning.png',
         'garment-conditioning.png', 'person-pose.png', 'garment-pose.png',
         'fidelity.json', 'reference-preparation.json', 'garment-prepared.png']


def retrieve(folder: Path):
    folder = folder.resolve()
    if not folder.is_relative_to(ROOT / 'experiments'):
        raise ValueError('Use an experiment directory')
    diagnostic = folder / 'vton-diagnostics.json'
    if not diagnostic.exists():
        diagnostic = folder / 'remote-failure.json'
    run = json.loads(diagnostic.read_text())['runPath']
    if not re.fullmatch(r'/content/formfit-online/runs/[0-9]+', run):
        raise ValueError('Invalid run path')
    pin = json.loads((ROOT / '.runtime/colab-autoconnect.json').read_text())['expectedHostname']
    # Keep replies below the notebook helper message limit.
    for start in range(0, len(NAMES), 4):
        names = NAMES[start:start+4]
        source = f'''import pathlib,socket,json,base64
if socket.gethostname()!={pin!r}:raise RuntimeError('Runtime changed; no artifacts read')
p=pathlib.Path({run!r})
print(json.dumps({{n:base64.b64encode((p/n).read_bytes()).decode() if (p/n).is_file() else None for n in {names!r}}}))
'''
        cell = call('add_code_cell', {'cellIndex': 0, 'language': 'python', 'code': source})['newCellId']
        reply = call('run_code_cell', {'cellId': cell})
        streams = ''.join(''.join(o.get('text', [])) for o in reply.get('outputs', []) if o.get('output_type') == 'stream')
        data = json.loads(streams.strip())
        for name in names:
            if data[name] is None:
                print('Unavailable:', name)
            else:
                (folder / name).write_bytes(base64.b64decode(data[name], validate=True))
                print('Recovered:', name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    retrieve(parser.parse_args().folder)
