import { createFileRoute, Link } from "@tanstack/react-router";
import { lazy, Suspense, useEffect, useState } from "react";
import { motion } from "motion/react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "geoheatAI — Urban Climate Intelligence" },
      {
        name: "description",
        content:
          "Quantifying urban heat. Engineering cooler cities. Thermal remote sensing, multi-variate regression, and physics-informed scenario modeling.",
      },
      { property: "og:title", content: "geoheatAI — Urban Climate Intelligence" },
      { property: "og:description", content: "Quantifying urban heat. Engineering cooler cities." },
    ],
  }),
  component: Home,
});

const Earth3D = lazy(() => import("@/components/Earth3D"));

function Nav() {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-black/60 backdrop-blur-md border-b border-[#1a1a1a]">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10 h-14 flex items-center justify-between">
        <a href="#top" className="flex items-center gap-2 font-sans text-[15px] font-semibold text-white">
          <span className="lowercase">geoheat<span className="text-[#F97316] font-black">AI</span></span>
          <span className="h-1.5 w-1.5 bg-[#F97316] rounded-full" aria-hidden />
        </a>
        <Link
          to="/app/map"
          className="font-mono text-[11px] uppercase text-[#a0a0a0] transition-colors hover:text-white"
        >
          Core Interface ↗
        </Link>
      </div>
    </header>
  );
}

/** 3D Earth — solid sphere with heat-band shader, slow auto-rotate */
function Hero() {
  return (
    <section id="top" className="relative border-b border-[#1a1a1a]">
      <div className="relative h-[88vh] min-h-[640px] w-full">
        {/* 3D canvas */}
        <div className="absolute inset-0">
          <Suspense fallback={<EarthFallback />}>
            <Earth3D />
          </Suspense>
        </div>

        {/* gradient mask for legibility */}
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,_transparent_30%,_rgba(0,0,0,0.85)_75%)]" />

        {/* overlay text */}
        <div className="relative z-10 h-full flex flex-col items-center justify-center text-center px-6">
          <h1 className="font-sans font-medium text-white text-[32px] sm:text-[42px] md:text-[56px] lg:text-[72px] leading-[1.15]">
            <span className="block whitespace-nowrap">
              Quantifying{" "}
              <span className="bg-gradient-to-r from-[#FBBF24] via-[#F97316] to-[#EF4444] bg-clip-text text-transparent">
                Urban Heat
              </span>
            </span>
            <span className="block whitespace-nowrap mt-1">
              Engineering{" "}
              <span className="bg-gradient-to-r from-[#FBBF24] via-[#F97316] to-[#EF4444] bg-clip-text text-transparent">
                Cooler Cities
              </span>
            </span>
          </h1>
          <p className="mt-10 max-w-xl text-[14px] text-[#a0a0a0] leading-relaxed">
            Thermal remote sensing, multi-variate regression, and physics-informed scenario
            modeling for the built environment.
          </p>
          <div className="mt-10 flex flex-col sm:flex-row gap-3">
            <a
              href="/app/map"
              className="bg-white text-black px-6 py-3 text-[13px] font-semibold hover:bg-[#F97316] hover:text-white transition-colors"
            >
              Access Core Interface →
            </a>
            <button className="border border-[#2a2a2a] text-white px-6 py-3 text-[13px] font-semibold hover:border-white transition-colors">
              View Methodology ↗
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function EarthFallback() {
  return (
    <div className="grid h-full w-full place-items-center bg-black">
      <div className="h-52 w-52 animate-pulse rounded-full border border-[#1a1a1a] bg-[#0a0a0a] shadow-[0_0_80px_rgba(249,115,22,0.18)]" />
    </div>
  );
}

const TICKER = [
  "+1.5°C GLOBAL THRESHOLD OVERLAPPED",
  "SURFACE ALBEDO DEFICIT IN MEGACITIES",
  "ANTHROPOGENIC HEAT FLUX ESCALATION",
  "NOCTURNAL UHI INTENSITY +3.8°C / DELHI",
  "VEGETATION CANOPY LOSS 12.4% / DECADE",
  "PEAK GRID LOAD +27% PER +1°C TMAX",
];

function Marquee() {
  const items = [...TICKER, ...TICKER];
  return (
    <div className="relative overflow-hidden border-b border-[#1a1a1a] py-5 bg-black">
      <motion.div
        className="flex gap-12 whitespace-nowrap font-sans font-semibold text-[22px] md:text-[32px]"
        animate={{ x: ["0%", "-50%"] }}
        transition={{ duration: 45, ease: "linear", repeat: Infinity }}
      >
        {items.map((t, i) => (
          <span key={i} className="flex items-center gap-12 text-white">
            <span className={i % 2 === 0 ? "text-[#F97316]" : ""}>{t}</span>
            <span className="text-[#2a2a2a]">●</span>
          </span>
        ))}
      </motion.div>
    </div>
  );
}

const RESEARCH = [
  {
    label: "THERMAL INERTIA",
    title: "Concrete remembers the sun.",
    body: "Dense urban masses absorb solar radiation through the day and release it at night, sustaining a heat island that elevates mortality risk after sundown.",
  },
  {
    label: "CANOPY DYNAMICS",
    title: "Canopy loss is non-linear.",
    body: "A small reduction in tree cover does not translate to a proportional rise in temperature. Past a critical threshold, cooling collapses and surface heat spikes.",
  },
  {
    label: "DISTRIBUTION IMPACT",
    title: "Heat is a distribution problem.",
    body: "Energy demand, hospital admissions, and lost labor concentrate in the same blocks. Vulnerability follows density, income, and access to shade.",
  },
];

function Research() {
  return (
    <section className="border-b border-[#1a1a1a]">
      <Marquee />
      <div className="mx-auto max-w-[1440px] px-6 md:px-10 py-24 md:py-32">
        <h2 className="font-sans font-semibold text-white text-[36px] md:text-[56px] leading-[1.1] max-w-4xl">
          Three vectors define the{" "}
          <span className="bg-gradient-to-r from-[#FBBF24] via-[#F97316] to-[#EF4444] bg-clip-text text-transparent">
            urban thermal regime
          </span>
          .
        </h2>

        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 md:divide-x divide-[#1f1f1f] border-t border-[#1f1f1f] pt-12">
          {RESEARCH.map((c, i) => (
            <div
              key={c.label}
              className={`px-0 md:px-10 py-8 md:py-2 ${i === 0 ? "md:pl-0" : ""} ${i === RESEARCH.length - 1 ? "md:pr-0" : ""}`}
            >
              <div className="font-mono text-[11px] tracking-wide text-white font-semibold">
                {c.label}
              </div>
              <h3 className="mt-6 font-sans font-semibold text-white text-[22px] md:text-[26px] leading-[1.25]">
                {c.title}
              </h3>
              <p className="mt-5 text-[14px] leading-[1.7] text-[#a0a0a0]">{c.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BarWidget() {
  const [data, setData] = useState<number[]>(() => Array.from({ length: 12 }, () => 30 + Math.random() * 70));
  useEffect(() => {
    const id = setInterval(() => {
      setData((d) => d.map((v) => Math.max(10, Math.min(100, v + (Math.random() - 0.5) * 22))));
    }, 900);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="w-full">
      <div className="flex items-end gap-1.5 h-32">
        {data.map((v, i) => {
          const color = v > 75 ? "#EF4444" : v > 55 ? "#F97316" : v > 35 ? "#FBBF24" : "#2a2a2a";
          return (
            <motion.div
              key={i}
              animate={{ height: `${v}%` }}
              transition={{ duration: 0.7, ease: "easeOut" }}
              className="flex-1"
              style={{ backgroundColor: color }}
            />
          );
        })}
      </div>
      <div className="mt-3 flex justify-between font-mono text-[10px] uppercase text-[#6b6b6b]">
        <span>ALBEDO</span>
        <span>DENSITY</span>
        <span>CANOPY</span>
      </div>
    </div>
  );
}

function MitigationMetric() {
  return (
    <div className="w-full">
      <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">Δ LST FORECAST</div>
      <div className="mt-4 flex items-baseline gap-3 flex-wrap">
        <span className="font-sans font-semibold text-[34px] md:text-[40px] leading-none text-white/50 line-through decoration-[#3a3a3a]">
          +4.2°C
        </span>
        <span className="font-mono text-[#6b6b6b]">→</span>
        <span className="font-sans font-semibold text-[44px] md:text-[60px] leading-none bg-gradient-to-r from-[#FBBF24] via-[#F97316] to-[#EF4444] bg-clip-text text-transparent">
          +1.1°C
        </span>
      </div>
      <div className="mt-6 border-t border-[#1f1f1f] pt-4 flex justify-between font-mono text-[11px] uppercase">
        <span className="text-[#6b6b6b]">NET IMPROVEMENT</span>
        <span className="text-white">−3.1°C</span>
      </div>
    </div>
  );
}

const TELEMETRY: Array<[string, string, boolean?]> = [
  ["SYS_LOC", "28.6139° N, 77.2090° E"],
  ["SCENE", "LC09_L2SP_146040_20260612"],
  ["LST_MAX", "47.32°C", true],
  ["POLYGONS", "14,228 active"],
  ["UPDATED", "06.16.26 · 14:22 UTC"],
];

function Telemetry() {
  return (
    <dl className="w-full font-mono text-[12px]">
      {TELEMETRY.map(([k, v, hot]) => (
        <div
          key={k}
          className="flex items-baseline justify-between gap-4 border-b border-[#1a1a1a] py-2.5"
        >
          <dt className="text-[#6b6b6b] uppercase">{k}</dt>
          <dd className={hot ? "text-[#F97316]" : "text-white"}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

const PHILOSOPHY = [
  {
    n: "01",
    title: "Hot-spot identification from orbit, indexed nightly.",
    body: "The pipeline ingests Landsat 8/9 TIRS and ECOSTRESS Level-2 LST tiles, performs atmospheric correction, regrids to a 30 m UTM lattice, and flags pixels exceeding adaptive nightly thresholds.",
    visual: <Telemetry />,
  },
  {
    n: "02",
    title: "Multi-variate SHAP separates signal from structure.",
    body: "A gradient-boosted regressor predicts pixel-level LST anomalies; SHAP value decomposition attributes the contribution of each driver — albedo, density, canopy, anthropogenic flux.",
    visual: <BarWidget />,
  },
  {
    n: "03",
    title: "Scenario modeling, grounded in physics not aesthetics.",
    body: "Candidate interventions — cool roofs, increased canopy, permeable paving — are injected into a coupled surface energy balance and CFD wind microclimate model.",
    visual: <MitigationMetric />,
  },
];

function Philosophy() {
  return (
    <section className="border-b border-[#1a1a1a]">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10 py-20 md:py-28">
        <h2 className="font-sans font-semibold text-white text-[36px] md:text-[56px] leading-[1.05] max-w-4xl">
          Identify. Quantify. <span className="text-[#F97316]">Mitigate.</span>
        </h2>

        <div className="mt-20 grid grid-cols-1 md:grid-cols-3 gap-12 md:gap-14 border-t border-[#1f1f1f] pt-14">
          {PHILOSOPHY.map((p) => (
            <div key={p.n} className="flex flex-col">
              <h3 className="font-sans font-semibold text-white text-[20px] md:text-[24px] leading-[1.3]">
                {p.title}
              </h3>
              <p className="mt-5 text-[14px] leading-[1.7] text-[#a0a0a0]">{p.body}</p>
              <div className="mt-10">{p.visual}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Footer() {
  const center = ["Dashboard", "Analysis", "Scenarios", "Export"];
  const right = ["LinkedIn", "GitHub", "Portfolio"];
  return (
    <footer className="border-t border-[#1f1f1f]">
      <div className="mx-auto max-w-[1440px] px-6 md:px-10 py-6 flex flex-col md:flex-row items-center justify-between gap-4 font-mono text-[11px] uppercase tracking-wide">
        <div className="text-white">
          geoheat<span className="text-[#F97316]">AI</span>
          <span className="text-[#6b6b6b]"> © 2026</span>
        </div>
        <nav className="flex items-center gap-3 text-[#a0a0a0]">
          {center.map((l, i) => (
            <span key={l} className="flex items-center gap-3">
              <a href="#" className="hover:text-white transition-colors">{l}</a>
              {i < center.length - 1 && <span className="text-[#3a3a3a]">|</span>}
            </span>
          ))}
        </nav>
        <nav className="flex items-center gap-3 text-[#a0a0a0]">
          {right.map((l, i) => (
            <span key={l} className="flex items-center gap-3">
              <a href="#" className="hover:text-white transition-colors">{l}</a>
              {i < right.length - 1 && <span className="text-[#3a3a3a]">|</span>}
            </span>
          ))}
        </nav>
      </div>
    </footer>
  );
}

function Home() {
  return (
    <div className="min-h-screen bg-black text-white font-sans">
      <Nav />
      <main className="pt-14">
        <Hero />
        <Research />
        <Philosophy />
      </main>
      <Footer />
    </div>
  );
}
