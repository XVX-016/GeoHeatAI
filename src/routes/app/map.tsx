
import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

const CITIES = ["Delhi NCR", "Mumbai", "Bengaluru", "Chennai", "Hyderabad"] as const;
const LAYER_CONFIG = [
  {
    name: "LST (Landsat 8)",
    description: "Land surface temperature from thermal satellite bands",
    colorClass: "bg-[#EF4444]",
    key: "lst",
  },
  {
    name: "NDVI",
    description: "Vegetation health and canopy cooling index",
    colorClass: "bg-[#22c55e]",
    key: "ndvi",
  },
  {
    name: "NDBI",
    description: "Built-up surface index for dense construction",
    colorClass: "bg-[#a78bfa]",
    key: "ndbi",
  },
  {
    name: "Building density",
    description: "Impervious mass and compact urban form",
    colorClass: "bg-[#FBBF24]",
    key: "density",
  },
  {
    name: "ERA5 air temp",
    description: "Regional atmospheric temperature baseline",
    colorClass: "bg-[#60a5fa]",
    key: "era5",
  },
] as const;

const PROGRESS_STEPS = [
  "FETCHING LANDSAT SCENES",
  "CLOUD MASKING",
  "ERA5 ALIGNMENT",
  "FEATURE EXTRACTION",
  "PIPELINE COMPLETE",
] as const;

export const Route = createFileRoute("/app/map")({
  component: MapPage,
});

function MapPage() {
  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
  });
  const isMockMode = healthData?.isMock ?? false;

  const [city, setCity] = useState<(typeof CITIES)[number]>("Delhi NCR");
  const [fromDate, setFromDate] = useState("2026-06-01");
  const [toDate, setToDate] = useState("2026-06-15");
  const [layers, setLayers] = useState({
    lst: true,
    ndvi: false,
    ndbi: false,
    density: false,
    era5: false,
  });
  const [cloudCover, setCloudCover] = useState(12);
  const [isRunning, setIsRunning] = useState(false);
  const [stepIndex, setStepIndex] = useState(-1);
  const [dotCount, setDotCount] = useState(0);
  const [viewMode, setViewMode] = useState<"BASELINE" | "OPTIMIZED">("BASELINE");

  useEffect(() => {
    let timeout: number | undefined;
    let interval: number | undefined;

    if (isRunning) {
      interval = window.setInterval(() => {
        setDotCount((count) => (count + 1) % 3);
      }, 400);

      if (stepIndex < PROGRESS_STEPS.length - 1) {
        timeout = window.setTimeout(() => {
          setStepIndex((current) => Math.min(current + 1, PROGRESS_STEPS.length - 1));
        }, 1100);
      } else {
        window.clearInterval(interval);
      }
    }

    return () => {
      if (timeout) window.clearTimeout(timeout);
      if (interval) window.clearInterval(interval);
    };
  }, [isRunning, stepIndex]);

  const progressEntries = useMemo(
    () =>
      PROGRESS_STEPS.map((step, index) => {
        const active = index === stepIndex && isRunning;
        const completed =
          index < stepIndex || (index === stepIndex && step === "PIPELINE COMPLETE");
        const textColor = completed ? "text-white" : "text-[#a0a0a0]";
        return (
          <div key={step} className={`font-mono text-[11px] leading-tight ${textColor}`}>
            {active && step !== "PIPELINE COMPLETE" ? `${step} ${".".repeat(dotCount + 1)}` : step}
          </div>
        );
      }),
    [dotCount, isRunning, stepIndex],
  );

  const startPipeline = () => {
    if (isRunning) return;
    setIsRunning(true);
    setStepIndex(0);
    setDotCount(0);
  };

  return (
    <div className="flex flex-col h-full min-h-[calc(100vh-3rem)] gap-4">
      {isMockMode && (
        <div className="bg-[#1a1a1a] border border-[#2a2a2a] px-4 py-2 font-mono text-[10px] text-[#6b6b6b] text-center">
          DEMO MODE · Representative Delhi NCR outputs · Run local backend for live satellite data
        </div>
      )}
      <div className="flex flex-1 gap-6">
        <aside className="w-[280px] flex-shrink-0 border-r border-[#1a1a1a] pr-5">
          <div className="space-y-6 py-4">
            <section className="space-y-4">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">LOCATION</div>
              <div className="space-y-4">
                <label className="block">
                  <span className="font-mono text-[10px] uppercase text-[#6b6b6b]">City</span>
                  <select
                    value={city}
                    onChange={(event) => setCity(event.target.value as (typeof CITIES)[number])}
                    className="mt-2 w-full rounded-none border border-[#1a1a1a] bg-black px-3 py-2 font-mono text-[12px] text-white outline-none focus:border-[#F97316]"
                  >
                    {CITIES.map((option) => (
                      <option key={option} value={option} className="bg-black text-white">
                        {option}
                      </option>
                    ))}
                  </select>
                </label>

                <div>
                  <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">Date range</div>
                  <p className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                    Satellite scene window for LST and index comparison.
                  </p>
                  <div className="mt-2 flex gap-3">
                    <label className="block w-full">
                      <span className="sr-only">From date</span>
                      <input
                        type="date"
                        value={fromDate}
                        onChange={(event) => setFromDate(event.target.value)}
                        aria-label="From date"
                        className="w-full rounded-none border border-[#1a1a1a] bg-black px-3 py-2 font-mono text-[12px] text-white outline-none focus:border-[#F97316]"
                      />
                    </label>
                    <label className="block w-full">
                      <span className="sr-only">To date</span>
                      <input
                        type="date"
                        value={toDate}
                        onChange={(event) => setToDate(event.target.value)}
                        aria-label="To date"
                        className="w-full rounded-none border border-[#1a1a1a] bg-black px-3 py-2 font-mono text-[12px] text-white outline-none focus:border-[#F97316]"
                      />
                    </label>
                  </div>
                </div>
              </div>
            </section>

            <section className="mt-4 space-y-4 border-t border-[#1a1a1a] pt-4">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">LAYERS</div>
              <div className="space-y-4">
                {LAYER_CONFIG.map((layer) => (
                  <div key={layer.key} className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <Switch
                        checked={layers[layer.key]}
                        onCheckedChange={(checked) =>
                          setLayers((current) => ({ ...current, [layer.key]: checked }))
                        }
                        className="mt-0.5 data-[state=checked]:bg-[#F97316]"
                      />
                      <div>
                        <div className="font-mono text-[11px] text-white">{layer.name}</div>
                        <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                          {layer.description}
                        </div>
                      </div>
                    </div>
                    <span className={`mt-1 h-3 w-3 flex-shrink-0 rounded-full ${layer.colorClass}`} />
                  </div>
                ))}
              </div>
            </section>

            <section className="space-y-4">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">PARAMETERS</div>
              <div className="space-y-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
                      Cloud cover threshold
                    </div>
                    <p className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                      Rejects scenes with too much cloud contamination.
                    </p>
                  </div>
                  <div className="font-mono text-[10px] text-[#F97316]">{cloudCover}%</div>
                </div>
                <Slider
                  value={[cloudCover]}
                  min={0}
                  max={30}
                  step={1}
                  onValueChange={([value]) => setCloudCover(value)}
                  className="h-6"
                >
                  <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
                    <Slider.Range className="absolute h-full bg-[#F97316]" />
                  </Slider.Track>
                  <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
                </Slider>
              </div>
            </section>

            <div className="space-y-3">
              <button
                type="button"
                onClick={startPipeline}
                className="w-full rounded-none bg-white px-4 py-3 font-mono text-[12px] uppercase tracking-wide text-black transition-colors hover:bg-[#F97316] hover:text-white"
              >
                RUN INGESTION
              </button>
              <div className="space-y-2">{progressEntries}</div>
            </div>
          </div>
        </aside>

        <section className="relative flex-1">
          <div className="relative h-full min-h-[calc(100vh-3rem)] overflow-hidden rounded-xl bg-[#0a0a0a]">
            <div className="absolute inset-0 grid place-items-center text-center font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
              MapLibre GL viewport centered on Delhi NCR: 28.6139°N, 77.2090°E
            </div>

            <div className="absolute right-6 top-6 flex items-center gap-2 rounded-full border border-[#1a1a1a] bg-black/80 p-1.5">
              {(["BASELINE", "OPTIMIZED"] as const).map((mode) => {
                const active = viewMode === mode;
                return (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setViewMode(mode)}
                    className={`rounded-full border border-[#1a1a1a] px-3 py-1 font-mono text-[10px] uppercase tracking-wide transition-colors ${active ? "bg-white text-black" : "bg-black text-[#a0a0a0]"
                      }`}
                  >
                    {mode}
                  </button>
                );
              })}
            </div>

            <div className="absolute bottom-28 left-6 w-60 rounded-xl border border-[#1a1a1a] bg-black/80 p-5">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">CURSOR</div>
              <div className="mt-2 font-mono text-[11px] text-white">28.6192°N 77.2198°E</div>
              <div className="mt-3 font-mono text-[13px] text-[#F97316]">42.3°C LST</div>
              <div className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                Rohini, Zone IV: sampled land surface temperature.
              </div>
            </div>

            <div className="absolute bottom-28 right-6 w-60 rounded-xl border border-[#1a1a1a] bg-black/80 p-5">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">LAND SURFACE TEMP</div>
              <div className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                LST scale from cooler surfaces to severe heat hotspots.
              </div>
              <div className="mt-4 h-2 w-44 rounded-full bg-gradient-to-r from-[#1d4ed8] via-[#FBBF24] to-[#EF4444]" />
              <div className="mt-3 flex justify-between font-mono text-[9px] text-[#a0a0a0]">
                <span>25°C</span>
                <span>40°C</span>
                <span>55°C</span>
              </div>
            </div>

            <Marker className="left-[20%] top-[24%]" label="ROHINI · 47°C LST" />
            <Marker className="left-[60%] top-[40%]" label="OKHLA · 45°C LST" />
            <Marker className="left-[45%] top-[70%]" label="SHAHDARA · 44°C LST" />
          </div>
        </section>
      </div>
    </div>
  );
}

function Marker({ className, label }: { className: string; label: string }) {
  return (
    <div className={`absolute ${className}`}>
      <div className="relative flex items-center gap-2">
        <div className="relative h-2.5 w-2.5 rounded-full bg-[#EF4444]">
          <span className="absolute inset-0 animate-ping rounded-full bg-[#EF4444]/40" />
        </div>
        <div className="rounded-md bg-black/60 px-2 py-1 font-mono text-[9px] text-[#F97316]">
          {label}
        </div>
      </div>
    </div>
  );
}
