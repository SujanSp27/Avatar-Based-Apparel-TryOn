import { useEffect, useRef, useState } from "react";
import { UserRound, Shirt, Plus, X } from "./icons";

export default function UploadCard({
  label,
  kind,
  file,
  onChange,
  disabled,
}: {
  label: string;
  kind: "person" | "garment";
  file?: File;
  onChange: (f?: File) => void;
  disabled: boolean;
}) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function choose(f?: File) {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) {
      setError("Choose a JPG, PNG or WebP.");
      return;
    }
    if (f.size > 12 * 1024 * 1024) {
      setError("Maximum file size is 12 MB.");
      return;
    }
    setError("");
    onChange(f);
  }
  return (
    <div className="upload-group">
      <span className="field-label">{label}</span>
      <input
        ref={input}
        aria-label={`Upload ${kind} image`}
        aria-describedby={
          kind === "person" ? "person-photo-guidance" : undefined
        }
        type="file"
        accept="image/jpeg,image/png,image/webp"
        disabled={disabled}
        onChange={(e) => choose(e.target.files?.[0])}
        className="file-input"
      />
      <div
        className={`upload-card ${file ? "has-file" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!disabled) choose(e.dataTransfer.files[0]);
        }}
      >
        <button
          className="upload-target"
          disabled={disabled}
          onClick={() => input.current?.click()}
          aria-label={`Choose ${kind} photo`}
        >
          {preview ? (
            <img src={preview} alt={`${kind} upload preview`} />
          ) : (
            <span className="upload-icon">
              {kind === "person" ? (
                <UserRound size={24} strokeWidth={1.4} />
              ) : (
                <Shirt size={24} strokeWidth={1.4} />
              )}
            </span>
          )}
          <span>
            <strong>
              {file
                ? file.name
                : `Add ${kind === "person" ? "your" : "garment"} photo`}
            </strong>
            <small>
              {file
                ? `${(file.size / 1024).toFixed(0)} KB · Click to replace`
                : kind === "person"
                  ? "Front-facing · torso visible"
                  : "Flat lay · plain background"}
            </small>
          </span>
          {!file && <Plus size={17} />}
        </button>
        {file && (
          <button
            className="remove-file"
            disabled={disabled}
            aria-label={`Remove ${kind} photo`}
            onClick={() => {
              onChange(undefined);
              if (input.current) input.current.value = "";
            }}
          >
            <X size={13} />
          </button>
        )}
      </div>
      {kind === "person" && (
        <p className="upload-guidance" id="person-photo-guidance">
          Show your face and the full region being dressed. Include legs and feet
          for trousers, skirts and dresses. Keep arms slightly apart.
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

