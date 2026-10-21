import { useEffect, useRef, useState } from "react";
const connections = [
  [0, 1],
  [1, 2],
  [2, 3],
  [3, 7],
  [0, 4],
  [4, 5],
  [5, 6],
  [6, 8],
  [9, 10],
  [11, 12],
  [11, 13],
  [13, 15],
  [15, 17],
  [15, 19],
  [17, 19],
  [15, 21],
  [12, 14],
  [14, 16],
  [16, 18],
  [16, 20],
  [18, 20],
  [16, 22],
  [11, 23],
  [12, 24],
  [23, 24],
  [23, 25],
  [25, 27],
  [27, 29],
  [29, 31],
  [27, 31],
  [24, 26],
  [26, 28],
  [28, 30],
  [30, 32],
  [28, 32],
];
export default function LandmarkCanvas({
  file,
  landmarks,
  show,
}: {
  file: File;
  landmarks?: number[][];
  show: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let disposed = false;
    setError("");
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      if (disposed || !canvas.current) return;
      const target = canvas.current;
      target.width = image.width;
      target.height = image.height;
      const ctx = target.getContext("2d")!;
      ctx.drawImage(image, 0, 0);
      if (show && landmarks?.length === 33) {
        ctx.strokeStyle = "#b4ff8c";
        ctx.lineWidth = Math.max(2, image.width / 350);
        for (const [a, b] of connections) {
          if (Math.min(landmarks[a][3], landmarks[b][3]) < 0.65) continue;
          ctx.beginPath();
          ctx.moveTo(
            landmarks[a][0] * image.width,
            landmarks[a][1] * image.height,
          );
          ctx.lineTo(
            landmarks[b][0] * image.width,
            landmarks[b][1] * image.height,
          );
          ctx.stroke();
        }
        landmarks.forEach(([x, y, , visibility], index) => {
          ctx.beginPath();
          ctx.arc(
            x * image.width,
            y * image.height,
            Math.max(3, image.width / 160),
            0,
            2 * Math.PI,
          );
          ctx.fillStyle = visibility > 0.65 ? "#f5ffc8" : "#cf8543";
          ctx.fill();
          ctx.fillStyle = "#123c32";
          ctx.font = `${Math.max(11, image.width / 65)}px sans-serif`;
          ctx.fillText(
            String(index),
            x * image.width + 8,
            y * image.height - 6,
          );
        });
      }
    };
    image.onerror = () => {
      if (!disposed) setError("The photo preview could not be loaded.");
    };
    image.src = url;
    return () => {
      disposed = true;
      image.onload = null;
      image.onerror = null;
      URL.revokeObjectURL(url);
    };
  }, [file, landmarks, show]);
  return (
    <>
      {error ? (
        <p role="alert">{error}</p>
      ) : (
        <canvas
          ref={canvas}
          className="landmark-canvas"
          role="img"
          aria-label={
            show && landmarks?.length
              ? "Your photo with all 33 pose landmarks; low visibility points are amber"
              : "Your uploaded full-body photo"
          }
        />
      )}
    </>
  );
}
