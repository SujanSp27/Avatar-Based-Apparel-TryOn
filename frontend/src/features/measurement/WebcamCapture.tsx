import { useEffect, useRef, useState } from "react";
import Modal from "../../components/ui/Modal";
import { ErrorNotice } from "../../components/feedback/Feedback";
import { prepareImage } from "../../utils/images";
function Camera({ onCapture }: { onCapture: (file: File) => void }) {
  const video = useRef<HTMLVideoElement>(null);
  const [error, setError] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => {
    let disposed = false;
    let stream: MediaStream | undefined;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        "Camera access requires a supported browser on HTTPS or localhost.",
      );
      return;
    }
    navigator.mediaDevices
      .getUserMedia({
        video: {
          facingMode: "environment",
          width: { ideal: 720 },
          height: { ideal: 1280 },
        },
        audio: false,
      })
      .then((value) => {
        stream = value;
        if (disposed) {
          value.getTracks().forEach((t) => t.stop());
          return;
        }
        if (video.current) {
          video.current.srcObject = value;
          void video.current.play();
        }
      })
      .catch(() =>
        setError(
          "Camera access was denied or unavailable. Upload a photo instead, or allow camera access in your browser.",
        ),
      );
    return () => {
      disposed = true;
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  return (
    <div className="stack">
      <p>
        Step back until your head and feet are visible. Keep arms slightly apart
        and use a contrasting background.
      </p>
      {error && <ErrorNotice message={error} />}
      <div className="camera-preview">
        <video
          ref={video}
          muted
          playsInline
          onLoadedData={() => setReady(true)}
          aria-label="Live camera preview"
        />
        <svg viewBox="0 0 200 400" aria-hidden="true">
          <circle cx="100" cy="48" r="24" />
          <path d="M76 83 L124 83 L142 198 L157 202 L140 100 Q130 78 124 83 M76 83 Q66 78 60 100 L43 202 L58 198 L76 83 M76 83 L72 218 L80 368 L94 368 L100 240 L106 368 L120 368 L128 218 L124 83" />
        </svg>
      </div>
      <button
        className="button"
        disabled={!ready}
        onClick={() => {
          const v = video.current!;
          const canvas = document.createElement("canvas");
          canvas.width = v.videoWidth;
          canvas.height = v.videoHeight;
          canvas.getContext("2d")!.drawImage(v, 0, 0);
          canvas.toBlob(
            async (blob) => {
              if (blob) {
                try {
                  onCapture(
                    await prepareImage(
                      new File([blob], "camera.jpg", { type: "image/jpeg" }),
                    ),
                  );
                } catch (e) {
                  setError((e as Error).message);
                }
              }
            },
            "image/jpeg",
            0.94,
          );
        }}
      >
        Capture photo
      </button>
    </div>
  );
}
export default function WebcamCapture({
  open,
  onClose,
  onCapture,
}: {
  open: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
}) {
  return (
    <Modal open={open} onClose={onClose} title="Capture your full-body photo">
      {open && (
        <Camera
          onCapture={(file) => {
            onCapture(file);
            onClose();
          }}
        />
      )}
    </Modal>
  );
}
