from dataclasses import dataclass
from typing import Protocol

import trimesh

from ml.preprocessing.images import ImageFeatures


@dataclass
class BodyResult:
    mesh: trimesh.Trimesh
    parameters: dict
    landmarks: dict
    provenance: dict


class HumanReconstructor(Protocol):
    def reconstruct(self, features: ImageFeatures, height_cm: float) -> BodyResult: ...
