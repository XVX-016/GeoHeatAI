import { Suspense, useMemo, useRef } from "react";
import { OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import * as THREE from "three";

function EarthMesh() {
  const ref = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.12;
  });

  const texture = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = 1024;
    c.height = 512;
    const ctx = c.getContext("2d")!;

    // Plain dark background — no colors, no glow
    ctx.fillStyle = "#050505";
    ctx.fillRect(0, 0, 1024, 512);

    // Latitude grid lines
    ctx.strokeStyle = "rgba(255,255,255,0.07)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 12; i++) {
      ctx.beginPath();
      ctx.moveTo(0, (512 / 12) * i);
      ctx.lineTo(1024, (512 / 12) * i);
      ctx.stroke();
    }

    // Longitude grid lines
    for (let i = 1; i < 24; i++) {
      ctx.beginPath();
      ctx.moveTo((1024 / 24) * i, 0);
      ctx.lineTo((1024 / 24) * i, 512);
      ctx.stroke();
    }

    const tex = new THREE.CanvasTexture(c);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
  }, []);

  return (
    <>
      <mesh ref={ref}>
        <sphereGeometry args={[1.6, 96, 96]} />
        <meshBasicMaterial map={texture} />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.605, 48, 32]} />
        <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.06} />
      </mesh>
    </>
  );
}

export default function Earth3D() {
  return (
    <Canvas
      camera={{ position: [0, 0, 4.2], fov: 45 }}
      dpr={[1, 2]}
      gl={{ antialias: true, alpha: true }}
    >
      <ambientLight intensity={0.3} />
      <Suspense fallback={null}>
        <EarthMesh />
      </Suspense>
      <OrbitControls enableZoom={false} enablePan={false} autoRotate={false} />
    </Canvas>
  );
}
