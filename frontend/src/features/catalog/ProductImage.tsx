import { useState } from "react";

/** A missing reference stays an error; it is never replaced by another garment. */
export default function ProductImage({
  src,
  alt,
  className,
}: {
  src: string;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState<string>();
  return failed === src ? (
    <span
      className="image-unavailable"
      role="img"
      aria-label={`${alt}: image unavailable`}
    >
      Photograph temporarily unavailable
    </span>
  ) : (
    <img
      className={className}
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(src)}
    />
  );
}
