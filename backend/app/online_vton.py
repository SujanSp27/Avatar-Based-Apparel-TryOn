"""Colab-only inference transport. This module must never import torch or CUDA.

Requests use the private, per-session token created by our Colab launcher. An
unavailable remote worker is an error, never a trigger for local inference.
"""
import base64
import io
import json
import time
from threading import Lock
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps, UnidentifiedImageError

from backend.app.config import settings
from ml.errors import PipelineError
from ml.progress import report_progress
from ml.vton.categories import MODEL_CATEGORIES

MAX_IMAGE_BYTES = 12 * 1024 * 1024


def normalized_image(data: bytes) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as source:
            if source.format not in {"PNG", "JPEG", "WEBP"}:
                raise ValueError("Use a JPG, PNG or WebP image.")
            if min(source.size) < 128 or source.width * source.height > 20_000_000:
                raise ValueError("Images must be at least 128 pixels per side and below 20 megapixels.")
            image = ImageOps.exif_transpose(source).convert("RGBA")
            image.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
            canvas = Image.new("RGB", image.size, "white")
            canvas.paste(image, mask=image.getchannel("A"))
            output = io.BytesIO()
            canvas.save(output, format="PNG", compress_level=2)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise PipelineError("invalid_image", str(exc) or "Image could not be decoded.") from exc


class OnlineTryOn:
    def __init__(self, url=None, token=None, *, transport=None):
        self.url = (settings.online_vton_url if url is None else url).rstrip("/")
        self.token = settings.online_vton_token if token is None else token
        self.transport = transport
        self.read_connection_file = url is None and token is None
        self._connection_lock = Lock()
        self._health_lock = Lock()
        self._checked_at = 0.
        self._checked_url = ""
        self._reachable = False

    def refresh_connection(self):
        if not self.read_connection_file or not settings.online_connection_path.is_file():
            return
        try:
            connection = json.loads(settings.online_connection_path.read_text(encoding="utf-8"))
            url, token = connection["url"].rstrip("/"), connection["token"]
            if not isinstance(token, str):
                raise ValueError("Invalid token")
            with self._connection_lock:
                self.url, self.token = url, token
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            with self._connection_lock:
                self.url, self.token = "", ""

    def credentials(self):
        self.refresh_connection()
        with self._connection_lock:
            return self.url, self.token

    def availability(self, *, check_connection=False):
        url, token = self.credentials()
        parsed = urlparse(url)
        configured = bool(
            parsed.scheme == "https" and parsed.hostname and not parsed.username
            and not parsed.password and not parsed.query and not parsed.fragment
            and len(token) >= 32
        )
        reachable = configured
        if configured and check_connection:
            with self._health_lock:
                if url != self._checked_url or time.monotonic() - self._checked_at > 10:
                    try:
                        with httpx.Client(timeout=4, follow_redirects=False, transport=self.transport) as client:
                            response = client.get(url + "/gradio_api/info")
                            self._reachable = response.status_code == 200 and "/generate" in response.json().get("named_endpoints", {})
                    except (httpx.HTTPError, ValueError, TypeError):
                        self._reachable = False
                    self._checked_at, self._checked_url = time.monotonic(), url
                reachable = self._reachable
        return {
            "available": reachable, "configured": configured, "backend": "FASHN VTON 1.5 / private Colab worker",
            "device": "online-gpu", "localGpuUsed": False,
            "supportedCategories": list(MODEL_CATEGORIES), "nativeResolution": [576, 864],
            "inferenceSteps": settings.online_vton_steps,
            "reason": (None if reachable else "The configured Colab worker is offline. Reconnect the existing runtime; local GPU inference is disabled.") if configured else "Connect the existing Colab GPU worker. Local GPU inference is disabled.",
            "availabilityType": "live-worker-check" if check_connection else "configuration-only",
        }

    def render(self, person: bytes, garment: bytes, category: str, photo_type: str, folder):
        if not self.availability()["available"]:
            raise PipelineError("online_gpu_unavailable", self.availability()["reason"], 503)
        if category not in MODEL_CATEGORIES or photo_type not in {"flat-lay", "model"}:
            raise PipelineError("garment_category", "Choose a supported garment and photo type.")
        person_png, garment_png = normalized_image(person), normalized_image(garment)
        (folder / "original-person.png").write_bytes(person_png)
        report_progress("uploading_online")
        start = time.perf_counter()
        # Keep the same worker for the whole event even if recovery rotates the
        # saved tunnel while generation is in progress. Never replay a POST.
        url, token = self.credentials()
        if not url or not token:
            raise PipelineError("online_gpu_unavailable", "The online worker is reconnecting automatically.", 503)
        data = [token, base64.b64encode(person_png).decode(),
                base64.b64encode(garment_png).decode(), MODEL_CATEGORIES[category],
                photo_type, settings.online_vton_steps]
        try:
            with httpx.Client(timeout=httpx.Timeout(settings.online_vton_timeout, connect=10),
                              follow_redirects=False, transport=self.transport) as client:
                response = client.post(url + "/gradio_api/call/generate", json={"data": data})
                response.raise_for_status()
                event_id = response.json()["event_id"]
                if not isinstance(event_id, str) or not event_id.isalnum() or len(event_id) > 100:
                    raise ValueError("Invalid remote event ID")
                # Persist before waiting: never resubmit automatically after a lost response.
                (folder / "remote-event.json").write_text(json.dumps({
                    "eventId": event_id, "url": url, "model": "FASHN VTON 1.5",
                }))
                report_progress("online_generating")
                with client.stream("GET", url + "/gradio_api/call/generate/" + event_id) as stream:
                    stream.raise_for_status()
                    event = ""
                    for line in stream.iter_lines():
                        if time.perf_counter() - start > settings.online_vton_timeout:
                            raise httpx.ReadTimeout("Online generation timed out")
                        if len(line) > 24 * 1024 * 1024:
                            raise ValueError("Remote result exceeds the response limit")
                        if line.startswith("event:"):
                            event = line[6:].strip()
                        elif line.startswith("data:"):
                            if event == "error":
                                raise PipelineError("online_gpu_failed", "The Colab worker rejected or could not finish this request. Check its runtime log; no local inference was started.", 502)
                            if event == "complete":
                                payload = json.loads(line[5:])[0]
                                break
                    else:
                        raise ValueError("Remote connection ended without a result")
                if payload.get("error"):
                    raise PipelineError(payload.get("code", "online_gpu_failed"), payload["error"], 422)
                if payload.get("model") != "FASHN VTON 1.5" or payload.get("device") != "cuda":
                    raise ValueError("Worker did not report the expected GPU model")
                output = base64.b64decode(payload["image"], validate=True)
                if len(output) > MAX_IMAGE_BYTES or not output.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Invalid generated PNG")
                with Image.open(io.BytesIO(output)) as image, Image.open(io.BytesIO(person_png)) as original:
                    image.load()
                    if image.size != original.size:
                        raise ValueError("Generated image dimensions do not match the original")
                (folder / "tryon-2d.png").write_bytes(output)
                diagnostics = {key: value for key, value in payload.items() if key != "image"}
                diagnostics["remoteRoundTripSeconds"] = round(time.perf_counter() - start, 3)
                (folder / "vton-diagnostics.json").write_text(json.dumps(diagnostics, indent=2))
                report_progress("saving_result")
                return diagnostics
        except PipelineError:
            raise
        except httpx.TimeoutException as exc:
            raise PipelineError("online_gpu_timeout", "Colab did not respond in time. The remote event ID was retained; no second generation or local GPU fallback was started.", 504) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError, OSError) as exc:
            raise PipelineError("online_gpu_connection", "Could not retrieve a valid result from the existing Colab worker. Reconnect its GPU runtime; local GPU inference is disabled.", 503) from exc
