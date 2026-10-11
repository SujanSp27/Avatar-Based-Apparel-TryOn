import json
from pathlib import Path

import pytest

from ml.human.template import MediaPipeTemplateReconstructor
from ml.preprocessing.images import PersonPreprocessor

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def chart_rows():
    return json.loads((ROOT / "data/brandCharts/demo-v1.json").read_text())["brands"][0]["sizes"]


@pytest.fixture(scope="session")
def processor():
    checkpoint = ROOT / "assets/bodyModels/pose_landmarker_full.task"
    if not checkpoint.exists():
        pytest.skip("Run scripts/download_assets.py first")
    return PersonPreprocessor(checkpoint)


@pytest.fixture(scope="session")
def person_features(processor):
    path = ROOT / "data/raw/studio-person.jpg"
    if not path.exists():
        pytest.skip("Download sample assets first")
    return processor.process(path.read_bytes())


@pytest.fixture(scope="session")
def body(person_features):
    return MediaPipeTemplateReconstructor().reconstruct(person_features, 172.0)
