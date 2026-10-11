"""Explicit optional HMR2 bridge. No fallback occurs if HMR2 is requested."""

from pathlib import Path

from ml.errors import PipelineError


class HMR2Reconstructor:
    """Gate research integration until a licensed model and upstream environment are available.

    Official APIs: hmr2.models.load_hmr2, hmr2.datasets.vitdet_dataset.ViTDetDataset;
    out['pred_vertices'], out['pred_smpl_params'], out['pred_cam'].
    See docs/model-adapter.md. This adapter deliberately reports unavailability instead of
    fabricating SMPL parameters or treating a canonical template as HMR2 inference.
    """

    def __init__(self, root: str, checkpoint: str, smpl_model: str):
        self.paths = {
            "HMR2_ROOT": root,
            "HMR2_CHECKPOINT": checkpoint,
            "SMPL_MODEL_PATH": smpl_model,
        }

    def reconstruct(self, features, height_cm):
        missing = [
            key for key, value in self.paths.items() if not value or not Path(value).exists()
        ]
        if missing:
            raise PipelineError(
                "hmr2_unavailable",
                "HMR2 requires official upstream environment and licensed SMPL asset. Missing: "
                + ", ".join(missing),
                503,
            )
        raise PipelineError(
            "hmr2_not_validated",
            "HMR2 assets exist but this adapter has not passed mesh/landmark calibration. Use the explicitly labelled mediapipe_template baseline.",
            503,
        )
