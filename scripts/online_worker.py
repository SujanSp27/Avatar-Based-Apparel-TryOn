"""Private Gradio worker, executed only in the user's existing Colab GPU runtime."""
import base64
import hashlib
import io
import json
import os
import secrets
import sys
import time
from collections import OrderedDict
from pathlib import Path
from threading import Lock

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.errors import PipelineError
from ml.vton.checked_sampler import CheckedSamplerMixin
from ml.vton.image_transport import encode_changed_pixels
from ml.vton.online_composite import preserve_regions
from ml.vton.region import inference_region, lower_body_visible

SOURCE = "7c0f10af3f91ad4048fe9729c470a13ef905d25a"
MODEL = "7720683168567eb5a2a4c67f15116c6e29c83ded"


class ArrayCache:
    """Bounded cache of deterministic parsing/pose, never of generated results."""
    def __init__(self, function, capacity=6):
        self.function, self.capacity = function, capacity
        self.values = OrderedDict()

    def __call__(self, array):
        key = (array.shape, array.dtype.str, hashlib.sha256(array.tobytes()).digest())
        if key not in self.values:
            self.values[key] = self.function(array)
            if len(self.values) > self.capacity:
                self.values.popitem(last=False)
        self.values.move_to_end(key)
        # Official preprocessing may modify returned label arrays.
        import copy
        return copy.deepcopy(self.values[key])


def main():
    if sys.platform != "linux" or not list(Path("/dev").glob("nvidia[0-9]*")):
        raise RuntimeError("This worker runs only on the connected Colab GPU, never locally.")
    # This pipeline uses PyTorch. Avoid loading an unrelated TensorFlow runtime
    # through transformers during cold startup.
    os.environ.setdefault("USE_TF", "0")
    import cv2
    import gradio as gr
    import torch
    from fashn_human_parser import FashnHumanParser
    from fashn_vton import TryOnPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("Colab CUDA is unavailable; CPU fallback is disabled.")
    root = Path("/content/formfit-online")
    token = (root / "worker-token.txt").read_text().strip()
    if len(token) < 32:
        raise RuntimeError("A private worker token is required")
    torch.set_num_threads(2)
    if torch.cuda.get_device_capability()[0] >= 8:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True

    profile = root / "worker-config.json"
    profile_data = json.loads(profile.read_text()) if profile.exists() else {}
    precision = profile_data.get("precision", "upstream")
    if precision not in {"upstream", "fp16"}:
        raise RuntimeError("Unsupported worker precision profile")
    use_fp16 = precision == "fp16" or os.environ.get("ONLINE_EXPERIMENTAL_FP16") == "1"
    resolution_profile = profile_data.get("resolution", "native")
    if resolution_profile not in {"native", "fast"}:
        raise RuntimeError("Unsupported worker resolution profile")
    # The pinned model uses convolutional patches and RoPE, with no learned
    # spatial embedding tied to the native grid. Keep the aspect ratio and
    # 12-pixel patch alignment. Reduced resolution requires visual evaluation.
    input_shape = (576, 384) if resolution_profile == "fast" else (864, 576)
    crop_person = profile_data.get("cropPerson", False)
    guidance = profile_data.get("guidanceScale", 1.5)
    if guidance not in {1.0, 1.5}:
        raise RuntimeError("Unsupported guidance profile")
    segmentation_free = profile_data.get("segmentationFree", True)

    class PinnedPipeline(CheckedSamplerMixin, TryOnPipeline):
        def _setup_tryon_model(self):
            if use_fp16:
                self.inference_dtype = torch.float16
            super()._setup_tryon_model()
            self.tryon_model.input_shape = input_shape

        def _setup_hp_model(self):
            self.hp_model = FashnHumanParser(model_id=str(root / "weights/parser"), device="cuda")

    pipeline = PinnedPipeline(weights_dir=str(root / "weights"), device="cuda")
    pipeline.skip_unused_unconditional = profile_data.get("skipUnusedUnconditional", False)
    pipeline.hp_model.predict = ArrayCache(pipeline.hp_model.predict)
    pipeline.pose_model = ArrayCache(pipeline.pose_model)
    environment = {"torch": torch.__version__, "cuda": torch.version.cuda,
                   "gpu": torch.cuda.get_device_name(), "capability": list(torch.cuda.get_device_capability()),
                   "dtype": str(pipeline.inference_dtype), "precisionProfile": precision,
                   "resolutionProfile": resolution_profile, "modelResolution": list(input_shape[::-1]),
                   "guidanceScale": guidance, "segmentationFree": segmentation_free,
                   "skipUnusedUnconditional": pipeline.skip_unused_unconditional,
                   "finitePredictionChecks": True, "finiteSamplerStateChecks": True}
    (root / "worker-environment.json").write_text(json.dumps(environment, indent=2))
    print("WORKER_ENVIRONMENT", json.dumps(environment), flush=True)
    lock = Lock()

    def generate(access_token, person_b64, garment_b64, category, photo_type, steps):
        if not secrets.compare_digest(str(access_token), token):
            raise gr.Error("Invalid worker token")
        if category not in {"tops", "bottoms", "one-pieces"} or photo_type not in {"model", "flat-lay"} or int(steps) not in {10, 15, 20, 30, 50}:
            return {"error": "Unsupported category, garment photo type or step count.", "code": "invalid_input"}
        if max(len(person_b64), len(garment_b64)) > 17 * 1024 * 1024:
            return {"error": "Images exceed the upload limit.", "code": "image_size"}
        with lock, torch.inference_mode():
            start = time.perf_counter()
            run = root / "runs" / str(time.time_ns())
            run.mkdir(parents=True)
            active = root / "active-generation.json"
            active.write_text(json.dumps({"pid": os.getpid(), "runPath": str(run), "startedAt": time.time()}))
            try:
                def decode(value):
                    raw = base64.b64decode(value, validate=True)
                    with Image.open(io.BytesIO(raw)) as image:
                        if min(image.size) < 128 or image.width * image.height > 2_000_000:
                            raise PipelineError("image_size", "Image dimensions are outside the worker limits.")
                        return image.convert("RGB")
                person, garment = decode(person_b64), decode(garment_b64)
                original = np.asarray(person)
                prepared_person = pipeline.pre_resize(person, allow_upsampling=False)
                labels = pipeline.hp_model.predict(np.asarray(prepared_person))
                labels = cv2.resize(labels, person.size, interpolation=cv2.INTER_NEAREST)
                Image.fromarray(labels.astype(np.uint8)).save(run / "source-labels.png")
                if category != "tops" and not lower_body_visible(labels):
                    raise PipelineError("lower_body_not_visible", "Show the full lower body for trousers, skirts, dresses and jumpsuits.")
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                crop = inference_region(labels, category) if crop_person else (0, 0, person.width, person.height)
                cropped_person = person.crop(crop)
                tick = time.perf_counter()
                preprocessing_seconds = tick - start
                generated_crop = pipeline(person_image=cropped_person, garment_image=garment, category=category,
                                     garment_photo_type=photo_type, num_samples=1, num_timesteps=int(steps),
                                     guidance_scale=guidance, seed=42, segmentation_free=segmentation_free).images[0]
                torch.cuda.synchronize()
                inference_seconds = time.perf_counter() - tick
                postprocessing_started = time.perf_counter()
                generated = original.copy()
                left, top, right, bottom = crop
                generated[top:bottom, left:right] = np.asarray(generated_crop.resize((right-left, bottom-top), Image.Resampling.LANCZOS))
                # Retain actual model output even if the preservation gate fails.
                Image.fromarray(generated).save(run / "raw.png")
                target = pipeline.hp_model.predict(generated)
                Image.fromarray(target.astype(np.uint8)).save(run / "target-labels.png")
                composite, alpha, review = preserve_regions(original, generated, labels, target, category)
                encoded, patch_metadata = encode_changed_pixels(person, Image.fromarray(composite))
                # Persist artifacts in Colab for actual visual review and recovery.
                Image.fromarray(composite).save(run / "result.png")
                Image.fromarray((alpha * 255).astype(np.uint8)).save(run / "edit-mask.png")
                diagnostics = {"model": "FASHN VTON 1.5", "sourceCommit": SOURCE,
                               "modelRevision": MODEL, "device": "cuda", "gpu": torch.cuda.get_device_name(),
                               "dtype": str(pipeline.inference_dtype), "steps": int(steps), "category": category,
                               "modelResolution": list(input_shape[::-1]),
                               "inferenceRegion": list(crop),
                               "environment": environment,
                               "inferenceSeconds": round(inference_seconds, 3),
                               "peakGpuAllocatedMB": round(torch.cuda.max_memory_allocated() / 1024**2, 1),
                               "workerSeconds": round(time.perf_counter() - start, 3),
                               "stageSeconds": {
                                   "preprocessing": round(preprocessing_seconds, 3),
                                   "generation": round(inference_seconds, 3),
                                   "postprocessingAndSaving": round(time.perf_counter() - postprocessing_started, 3),
                               },
                               "cache": "bounded pose/parser cache; every result is a fresh generation",
                               "preservation": review, "runPath": str(run)}
                (run / "report.json").write_text(json.dumps(diagnostics, indent=2))
                return {**diagnostics, **patch_metadata, "imageFormat": "webp", "image": base64.b64encode(encoded).decode()}
            except PipelineError as exc:
                failure = {"code": exc.code, "message": str(exc), "model": "FASHN VTON 1.5",
                           "modelRevision": MODEL, "runPath": str(run), "category": category,
                           "steps": int(steps), "workerSeconds": round(time.perf_counter() - start, 3)}
                (run / "failure.json").write_text(json.dumps(failure, indent=2))
                return {**failure, "error": str(exc)}
            except Exception as exc:
                print(type(exc).__name__, str(exc), flush=True)
                failure = {"code": "online_inference_failed", "type": type(exc).__name__,
                           "model": "FASHN VTON 1.5", "modelRevision": MODEL,
                           "runPath": str(run), "category": category, "steps": int(steps),
                           "workerSeconds": round(time.perf_counter() - start, 3)}
                (run / "failure.json").write_text(json.dumps(failure, indent=2))
                return {**failure, "error": "The online model could not process this image. See the Colab worker log."}
            finally:
                active.unlink(missing_ok=True)

    with gr.Blocks(analytics_enabled=False) as app:
        args = [gr.Textbox(visible=False) for _ in range(5)] + [gr.Number(value=20, visible=False)]
        output = gr.JSON(visible=False)
        gr.Button("Private API").click(generate, inputs=args, outputs=output, api_name="generate", concurrency_limit=1)
    _, _, url = app.queue(max_size=2).launch(share=True, server_name="127.0.0.1", prevent_thread_lock=True, show_api=False, quiet=True)
    (root / "connection.json").write_text(json.dumps({"url": url, "gpu": torch.cuda.get_device_name(),
                                                    "model": MODEL, "modelResolution": list(input_shape[::-1]),
                                                    "precision": str(pipeline.inference_dtype)}))
    print("ONLINE_VTON_READY", flush=True)
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
