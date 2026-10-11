import {
  Component,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { Canvas, useThree } from "@react-three/fiber";
import { ContactShadows } from "@react-three/drei/core/ContactShadows";
import { Grid } from "@react-three/drei/core/Grid";
import { Html } from "@react-three/drei/web/Html";
import { OrbitControls } from "@react-three/drei/core/OrbitControls";
import { useGLTF } from "@react-three/drei/core/Gltf";
import { Box3, Group, Vector3 } from "three";
import type { OrbitControls as OrbitControlsType } from "three-stdlib";
import { Expand, RotateCw, Download, Move, ZoomIn } from "./icons";

type View = "front" | "side" | "back";

class ModelBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <Html center>
        <div className="viewer-error" role="alert">
          The 3D asset could not be loaded. Download it to inspect, or generate
          again.
        </div>
      </Html>
    ) : (
      this.props.children
    );
  }
}

function Model({ url, onLoad }: { url: string; onLoad: () => void }) {
  const { scene } = useGLTF(url);
  const ref = useRef<Group>(null);
  useEffect(() => {
    const bounds = new Box3().setFromObject(scene);
    if (!Number.isFinite(bounds.max.y) || bounds.isEmpty())
      throw new Error("Invalid GLB bounds");
    scene.traverse((object) => {
      object.castShadow = true;
      object.receiveShadow = true;
    });
    onLoad();
  }, [scene, onLoad]);
  return (
    <group ref={ref}>
      <primitive object={scene} />
    </group>
  );
}

function ViewControls({
  view,
  spin,
  resetKey,
}: {
  view: View;
  spin: boolean;
  resetKey: number;
}) {
  const { camera, invalidate } = useThree();
  const controls = useRef<OrbitControlsType>(null);
  useEffect(() => {
    const positions = {
      front: [0, 1.2, 3.1],
      side: [3.1, 1.2, 0],
      back: [0, 1.2, -3.1],
    };
    camera.position.fromArray(positions[view]);
    camera.lookAt(new Vector3(0, 0.87, 0));
    controls.current?.target.set(0, 0.87, 0);
    controls.current?.update();
    invalidate();
  }, [camera, invalidate, view, resetKey]);
  return (
    <OrbitControls
      ref={controls}
      makeDefault
      target={[0, 0.87, 0]}
      enablePan={false}
      minDistance={1.3}
      maxDistance={5}
      maxPolarAngle={Math.PI * 0.7}
      autoRotate={spin}
      autoRotateSpeed={1.6}
    />
  );
}

function EmptyMannequin() {
  return (
    <group position={[0, 0.04, 0]}>
      <mesh position={[0, 1.51, 0]} scale={[0.105, 0.135, 0.1]}>
        <sphereGeometry args={[1, 24, 24]} />
        <meshStandardMaterial
          color="#c5caba"
          transparent
          opacity={0.4}
          wireframe
        />
      </mesh>
      <mesh position={[0, 1.14, 0]} scale={[0.21, 0.3, 0.12]}>
        <sphereGeometry args={[1, 24, 24]} />
        <meshStandardMaterial
          color="#c5caba"
          transparent
          opacity={0.4}
          wireframe
        />
      </mesh>
      {[-1, 1].map((sign) => (
        <group key={sign}>
          <mesh position={[sign * 0.115, 0.49, 0]}>
            <capsuleGeometry args={[0.075, 0.68, 8, 16]} />
            <meshStandardMaterial
              color="#c5caba"
              transparent
              opacity={0.35}
              wireframe
            />
          </mesh>
          <mesh
            position={[sign * 0.29, 1.06, 0]}
            rotation={[0, 0, sign * 0.22]}
          >
            <capsuleGeometry args={[0.046, 0.47, 8, 16]} />
            <meshStandardMaterial
              color="#c5caba"
              transparent
              opacity={0.35}
              wireframe
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}

export default function Viewer({
  url,
  busy,
  loaded,
  onLoad,
}: {
  url?: string;
  busy: boolean;
  loaded: boolean;
  onLoad: () => void;
}) {
  const [view, setView] = useState<View>("front");
  const [spin, setSpin] = useState(false);
  const [resetKey, setResetKey] = useState(0);
  const container = useRef<HTMLDivElement>(null);
  const [webgl, setWebgl] = useState(true);
  useEffect(() => {
    const c = document.createElement("canvas");
    setWebgl(!!(c.getContext("webgl2") || c.getContext("webgl")));
  }, []);
  return (
    <div
      className="viewer"
      ref={container}
      data-testid="viewer"
      data-loaded={loaded}
    >
      <div className="viewer-top">
        <span className="eyebrow">
          {url ? "YOUR 3D AVATAR" : "3D FITTING ROOM"}
        </span>
        <button
          className="icon-button"
          title="Full screen"
          aria-label="Full screen viewer"
          onClick={() => {
            if (document.fullscreenElement) void document.exitFullscreen();
            else void container.current?.requestFullscreen();
          }}
        >
          <Expand size={17} />
        </button>
      </div>
      {webgl ? (
        <Canvas
          shadows
          frameloop={spin ? "always" : "demand"}
          dpr={[1, 1.5]}
          camera={{ position: [0, 1.2, 3.1], fov: 40 }}
          gl={{ antialias: true, preserveDrawingBuffer: true }}
        >
          <color attach="background" args={["#e9ece2"]} />
          <ambientLight intensity={1.5} />
          <directionalLight position={[3, 5, 4]} intensity={2.2} castShadow />
          <directionalLight position={[-3, 2, -2]} intensity={1.2} />
          <ModelBoundary key={url}>
            <Suspense
              fallback={
                <Html center>
                  <span className="canvas-loading">Loading 3D asset…</span>
                </Html>
              }
            >
              {url ? <Model url={url} onLoad={onLoad} /> : <EmptyMannequin />}
            </Suspense>
          </ModelBoundary>
          <ContactShadows
            key={`${url ?? "placeholder"}-${loaded}`}
            frames={1}
            position={[0, -0.01, 0]}
            opacity={0.3}
            scale={5}
            blur={2.5}
            far={2}
          />
          <Grid
            position={[0, -0.015, 0]}
            args={[8, 8]}
            cellSize={0.25}
            cellThickness={0.5}
            cellColor="#cad0c2"
            sectionSize={1}
            sectionThickness={0.5}
            sectionColor="#bfc7b6"
            fadeDistance={5}
            fadeStrength={2}
          />
          <ViewControls view={view} spin={spin} resetKey={resetKey} />
        </Canvas>
      ) : (
        <div className="no-webgl" role="alert">
          WebGL is unavailable in this browser. Enable hardware acceleration to
          view the avatar. Generated assets are still downloadable.
        </div>
      )}
      {!url && !busy && (
        <div className="empty-view">
          <span>Made to see the whole picture.</span>
          <p>Add your photos to generate an approximate avatar.</p>
        </div>
      )}
      {busy && (
        <div className="busy-view" role="status">
          <div className="spinner" />
          <strong>Building your try-on</strong>
          <p>Processing images and generating your selected try-on…</p>
        </div>
      )}
      <div className="viewer-bottom">
        <div className="view-tabs">
          {(["front", "side", "back"] as View[]).map((v) => (
            <button
              key={v}
              aria-pressed={view === v}
              className={view === v ? "active" : ""}
              onClick={() => {
                setView(v);
                setSpin(false);
                setResetKey((k) => k + 1);
              }}
            >
              {v}
            </button>
          ))}
          <button
            aria-label="Rotate 360 degrees"
            aria-pressed={spin}
            className={spin ? "active" : ""}
            onClick={() => setSpin(!spin)}
          >
            <RotateCw size={14} />
            360°
          </button>
        </div>
        <div className="viewer-hints">
          <span>
            <Move size={13} />
            Drag to rotate
          </span>
          <span>
            <ZoomIn size={13} />
            Scroll to zoom
          </span>
        </div>
      </div>
      {url && (
        <a className="download-model" href={url} download>
          <Download size={14} />
          GLB
        </a>
      )}
    </div>
  );
}
