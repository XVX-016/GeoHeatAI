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
    const g = ctx.createLinearGradient(0, 0, 0, 512);
    g.addColorStop(0, "#0a0a0a");
    g.addColorStop(0.45, "#1a1a1a");
    g.addColorStop(0.5, "#3a1410");
    g.addColorStop(0.55, "#1a1a1a");
    g.addColorStop(1, "#0a0a0a");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 1024, 512);

    const eq = ctx.createLinearGradient(0, 200, 0, 312);
    eq.addColorStop(0, "rgba(251,191,36,0)");
    eq.addColorStop(0.5, "rgba(239,68,68,0.55)");
    eq.addColorStop(1, "rgba(251,191,36,0)");
    ctx.fillStyle = eq;
    ctx.fillRect(0, 200, 1024, 112);

    const blobs = [
      [180, 220, 80, "#EF4444"],
      [340, 180, 60, "#F97316"],
      [520, 260, 95, "#EF4444"],
      [700, 200, 55, "#FBBF24"],
      [850, 290, 70, "#F97316"],
      [120, 320, 45, "#FBBF24"],
      [620, 150, 40, "#F97316"],
    ] as const;

    for (const [x, y, r, col] of blobs) {
      const rg = ctx.createRadialGradient(x, y, 0, x, y, r);
      rg.addColorStop(0, col);
      rg.addColorStop(0.4, `${col}88`);
      rg.addColorStop(1, "transparent");
      ctx.fillStyle = rg;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 1; i < 12; i++) {
      ctx.beginPath();
      ctx.moveTo(0, (512 / 12) * i);
      ctx.lineTo(1024, (512 / 12) * i);
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
        <meshStandardMaterial map={texture} roughness={0.85} metalness={0.05} />
      </mesh>
      <mesh>
        <sphereGeometry args={[1.605, 48, 32]} />
        <meshBasicMaterial color="#ffffff" wireframe transparent opacity={0.04} />
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
      <ambientLight intensity={0.55} />
      <directionalLight position={[5, 3, 5]} intensity={1.2} color="#fff1e0" />
      <directionalLight position={[-5, -2, -3]} intensity={0.3} color="#F97316" />
      <Suspense fallback={null}>
        <EarthMesh />
      </Suspense>
      <OrbitControls enableZoom={false} enablePan={false} autoRotate={false} />
    </Canvas>
  );
}
