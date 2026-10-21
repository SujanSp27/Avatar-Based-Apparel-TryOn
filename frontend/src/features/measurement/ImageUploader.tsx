import { useId, useRef, useState } from "react";
import { Upload, X, Check } from "../../icons";
import { prepareImage } from "../../utils/images";
import { ErrorNotice } from "../../components/feedback/Feedback";
export default function ImageUploader({
  file,
  onChange,
  label = "Your full-body photo",
  disabled = false,
}: {
  file?: File;
  onChange: (file: File | undefined) => void;
  label?: string;
  disabled?: boolean;
}) {
  const id = useId();
  const ref = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [drag, setDrag] = useState(false);
  async function choose(candidate?: File) {
    if (!candidate || disabled) return;
    setError("");
    setBusy(true);
    try {
      onChange(await prepareImage(candidate));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      if (ref.current) ref.current.value = "";
    }
  }
  return (
    <div>
      <div
        className={`upload-zone ${drag ? "drag-active" : ""} ${file ? "upload-filled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          void choose(e.dataTransfer.files[0]);
        }}
      >
        <input
          ref={ref}
          id={id}
          className="visually-hidden"
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label={label}
          disabled={disabled || busy}
          onChange={(e) => void choose(e.target.files?.[0])}
        />
        <label htmlFor={id} className="upload-target">
          <span className="upload-icon">
            {file ? <Check size={22} /> : <Upload size={22} />}
          </span>
          <strong>
            {busy ? "Preparing image…" : file ? file.name : label}
          </strong>
          <span>
            {file
              ? `${Math.round(file.size / 1024)} KB · Click to replace`
              : "Drop an image here or browse files"}
          </span>
          <small>JPEG, PNG or WebP · Up to 10 MB</small>
        </label>
        {file && !disabled && (
          <button
            type="button"
            className="upload-remove icon-button"
            aria-label={`Remove ${label}`}
            onClick={() => onChange(undefined)}
          >
            <X size={16} />
          </button>
        )}
      </div>
      {error && <ErrorNotice message={error} />}
    </div>
  );
}
