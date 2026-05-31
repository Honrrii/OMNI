import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

// Backend origin for resolving relative asset_url paths.
const BACKEND_ORIGIN = "http://127.0.0.1:8000";

function resolveUrl(assetUrl) {
  if (!assetUrl) return null;
  if (assetUrl.startsWith("http://") || assetUrl.startsWith("https://")) {
    return assetUrl;
  }
  return `${BACKEND_ORIGIN}${assetUrl}`;
}

export default function VisualBayGlbViewer({ asset }) {
  const mountRef        = useRef(null);
  const resetCameraRef  = useRef(null);   // set after load; cleared on cleanup
  const [error,  setError]  = useState(null);
  const [loaded, setLoaded] = useState(false);

  const fullUrl = resolveUrl(asset?.asset_url);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !fullUrl) return;

    setError(null);
    setLoaded(false);
    resetCameraRef.current = null;

    const width  = mount.clientWidth  || 600;
    const height = mount.clientHeight || 380;

    // ── Renderer ──────────────────────────────────────────────
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    mount.appendChild(renderer.domElement);

    // ── Scene ─────────────────────────────────────────────────
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x01030a);

    // ── Camera ────────────────────────────────────────────────
    const camera = new THREE.PerspectiveCamera(45, width / height, 0.001, 2000);
    camera.position.set(0, 1.2, 3);

    // ── Lights ────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0xffffff, 0.7));
    const dir = new THREE.DirectionalLight(0xffffff, 1.2);
    dir.position.set(5, 10, 7.5);
    scene.add(dir);
    const fill = new THREE.DirectionalLight(0x8ab4ff, 0.4);
    fill.position.set(-5, 2, -5);
    scene.add(fill);

    // ── OrbitControls ─────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan     = true;
    controls.enableZoom    = true;

    // ── Load GLB/GLTF ─────────────────────────────────────────
    const loader = new GLTFLoader();
    loader.load(
      fullUrl,
      (gltf) => {
        const box    = new THREE.Box3().setFromObject(gltf.scene);
        const center = box.getCenter(new THREE.Vector3());
        const size   = box.getSize(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;

        // Center model at origin.
        gltf.scene.position.sub(center);

        // Frame camera to fit the bounding box.
        const dist = maxDim * 2.2;
        camera.position.set(0, maxDim * 0.4, dist);
        camera.near = dist * 0.001;
        camera.far  = dist * 20;
        camera.updateProjectionMatrix();
        controls.target.set(0, 0, 0);
        controls.update();

        // Capture fitted state so Reset camera can restore it without reloading.
        const fitX    = camera.position.x;
        const fitY    = camera.position.y;
        const fitZ    = camera.position.z;
        const fitNear = camera.near;
        const fitFar  = camera.far;

        resetCameraRef.current = () => {
          camera.position.set(fitX, fitY, fitZ);
          camera.near = fitNear;
          camera.far  = fitFar;
          camera.updateProjectionMatrix();
          controls.target.set(0, 0, 0);
          controls.update();
        };

        scene.add(gltf.scene);
        setLoaded(true);
      },
      undefined,
      (_err) => {
        setError(
          "Model could not be loaded for preview. " +
          "No data was modified. Check that the export folder is accessible."
        );
      }
    );

    // ── Render loop ───────────────────────────────────────────
    let animId;
    const animate = () => {
      animId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // ── Resize handling ───────────────────────────────────────
    const ro = new ResizeObserver(() => {
      const w = mount.clientWidth;
      const h = mount.clientHeight;
      if (!w || !h) return;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    });
    ro.observe(mount);

    // ── Cleanup on unmount or asset change ────────────────────
    return () => {
      resetCameraRef.current = null;
      cancelAnimationFrame(animId);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [fullUrl]);

  return (
    <div className="vb-glb-viewer">
      <div ref={mountRef} className="vb-glb-viewer-stage" />

      {!loaded && !error && (
        <p className="vb-glb-viewer-note vb-glb-viewer-loading">
          Loading browser preview…
        </p>
      )}
      {error && (
        <p className="vb-glb-viewer-error">{error}</p>
      )}

      {loaded && (
        <div className="vb-glb-viewer-controls">
          <button
            type="button"
            className="vb-glb-viewer-button"
            onClick={() => resetCameraRef.current?.()}
            aria-label="Reset camera to fit view"
          >
            Reset camera
          </button>
        </div>
      )}

      <div className="vb-glb-viewer-help">
        <span>Drag to inspect placeholder.</span>
        <span>Scroll to zoom.</span>
        <span>Browser visualization only.</span>
      </div>

      <p className="vb-glb-viewer-note">
        Browser visualization only. Placeholder geometry may not represent the generated CAD or robot structure.
        No engineering validation implied.
        No simulation launched.
        No scripts executed.
      </p>
    </div>
  );
}
