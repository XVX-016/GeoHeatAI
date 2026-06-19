import { useEffect, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";

const interventionOptions = {
  greening: ["STREET TREES", "PARKS", "GREEN ROOFS", "MIXED"] as const,
  roofs: ["WHITE PAINT", "REFLECTIVE MEM.", "VEGETATION"] as const,
  blue: ["HOTSPOT-ADJ.", "DRAINAGE", "PARKS"] as const,
};

const loadingSteps = [
  "EVALUATING 2,400 CANDIDATE SOLUTIONS",
  "SOLVING NSGA-III PARETO FRONT",
  "GENERATING INTERVENTION MAP",
  "✓ OPTIMIZATION COMPLETE",
] as const;

export const Route = createFileRoute("/app/scenarios")({
  component: ScenariosPage,
});

function ScenariosPage() {
  const [greeningEnabled, setGreeningEnabled] = useState(true);
  const [greeningValue, setGreeningValue] = useState(20);
  const [greeningType, setGreeningType] = useState<typeof interventionOptions.greening[number]>(
    "MIXED",
  );

  const [roofValue, setRoofValue] = useState(0.65);
  const [roofCoverage, setRoofCoverage] = useState(60);
  const [roofType, setRoofType] = useState<typeof interventionOptions.roofs[number]>(
    "REFLECTIVE MEM.",
  );

  const [blueEnabled, setBlueEnabled] = useState(false);
  const [blueArea, setBlueArea] = useState(0);
  const [blueType, setBlueType] = useState<typeof interventionOptions.blue[number]>(
    "DRAINAGE",
  );

  const [running, setRunning] = useState(false);
  const [progressIndex, setProgressIndex] = useState(-1);
  const [dotCount, setDotCount] = useState(0);

  useEffect(() => {
    let interval: number | undefined;
    let timeout: number | undefined;

    if (running) {
      interval = window.setInterval(() => {
        setDotCount((count) => (count + 1) % 3);
      }, 400);

      if (progressIndex < loadingSteps.length - 1) {
        timeout = window.setTimeout(() => {
          setProgressIndex((index) => Math.min(index + 1, loadingSteps.length - 1));
        }, 1100);
      } else {
        window.clearInterval(interval);
      }
    }

    return () => {
      if (interval) window.clearInterval(interval);
      if (timeout) window.clearTimeout(timeout);
    };
  }, [running, progressIndex]);

  const steps = useMemo(
    () =>
      loadingSteps.map((step, idx) => {
        const active = idx === progressIndex && running;
        const completed = idx < progressIndex || (!running && idx === loadingSteps.length - 1);
        return (
          <div
            key={step}
            className={`font-mono text-[10px] ${
              step === loadingSteps[loadingSteps.length - 1] && completed
                ? "text-white"
                : "text-[#6b6b6b]"
            }`}
          >
            {active && step !== loadingSteps[loadingSteps.length - 1]
              ? `${step} ${".".repeat(dotCount + 1)}`
              : step}
          </div>
        );
      }),
    [dotCount, running, progressIndex],
  );

  const deployGreening = (type: typeof interventionOptions.greening[number]) =>
    setGreeningType(type);
  const deployRoof = (type: typeof interventionOptions.roofs[number]) => setRoofType(type);
  const deployBlue = (type: typeof interventionOptions.blue[number]) => setBlueType(type);

  const startOptimization = () => {
    if (running) return;
    setRunning(true);
    setProgressIndex(0);
    setDotCount(0);
  };

  const showResults = progressIndex === loadingSteps.length - 1;

  return (
    <div className="flex min-h-full">
      <aside className="w-[360px] shrink-0 border-r border-[#1a1a1a] px-6 py-6 overflow-y-auto">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
          INTERVENTION CONTROLS
        </div>

        <InterventionCard disabled={false} className="mt-6">
          <CardHeader title="URBAN GREENING" enabled={greeningEnabled} onToggle={setGreeningEnabled} />
          <CardLabel label="NDVI INCREASE TARGET" />
          <SliderField value={`${greeningValue}%`}>
            <Slider
              value={[greeningValue]}
              min={0}
              max={50}
              step={1}
              onValueChange={([value]) => setGreeningValue(value)}
              className="h-6"
            >
              <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
                <Slider.Range className="absolute h-full bg-[#F97316]" />
              </Slider.Track>
              <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
            </Slider>
          </SliderField>
          <CardLabel label="INTERVENTION TYPE" />
          <div className="mt-2 flex flex-wrap gap-2">
            {interventionOptions.greening.map((type) => (
              <Chip
                key={type}
                active={type === greeningType}
                onClick={() => deployGreening(type)}
              >
                {type}
              </Chip>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-[#6b6b6b]">
            <span>EST. COST</span>
            <span className="text-white">₹ 12,400 CR</span>
          </div>
          <div className="mt-2 font-mono text-[12px] text-[#1D9E75]">
            −1.5°C TO −3.0°C REDUCTION
          </div>
        </InterventionCard>

        <InterventionCard className="mt-6">
          <CardHeader title="COOL ROOFS" enabled onToggle={() => undefined} />
          <CardLabel label="ALBEDO TARGET" />
          <SliderField value={roofValue.toFixed(2)}>
            <Slider
              value={[roofValue]}
              min={0.2}
              max={0.85}
              step={0.01}
              onValueChange={([value]) => setRoofValue(Number(value.toFixed(2)))}
              className="h-6"
            >
              <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
                <Slider.Range className="absolute h-full bg-[#F97316]" />
              </Slider.Track>
              <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
            </Slider>
          </SliderField>
          <CardLabel label="BUILDING COVERAGE" />
          <SliderField value={`${roofCoverage}%`}>
            <Slider
              value={[roofCoverage]}
              min={0}
              max={100}
              step={1}
              onValueChange={([value]) => setRoofCoverage(value)}
              className="h-6"
            >
              <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
                <Slider.Range className="absolute h-full bg-[#F97316]" />
              </Slider.Track>
              <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
            </Slider>
          </SliderField>
          <CardLabel label="MATERIAL TYPE" />
          <div className="mt-2 flex flex-wrap gap-2">
            {interventionOptions.roofs.map((type) => (
              <Chip key={type} active={type === roofType} onClick={() => deployRoof(type)}>
                {type}
              </Chip>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-[#6b6b6b]">
            <span>EST. COST</span>
            <span className="text-white">₹ 8,200 CR</span>
          </div>
          <div className="mt-2 font-mono text-[12px] text-[#1D9E75]">
            −0.5°C TO −2.0°C REDUCTION
          </div>
        </InterventionCard>

        <InterventionCard disabled={!blueEnabled} className="mt-6">
          <CardHeader title="BLUE INFRASTRUCTURE" enabled={blueEnabled} onToggle={setBlueEnabled} />
          <CardLabel label="WATER BODY AREA" />
          <SliderField value={`${blueArea} ha`}>
            <Slider
              value={[blueArea]}
              min={0}
              max={800}
              step={10}
              onValueChange={([value]) => setBlueArea(value)}
              className="h-6"
            >
              <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
                <Slider.Range className="absolute h-full bg-[#F97316]" />
              </Slider.Track>
              <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
            </Slider>
          </SliderField>
          <CardLabel label="PLACEMENT" />
          <div className="mt-2 flex flex-wrap gap-2">
            {interventionOptions.blue.map((type) => (
              <Chip key={type} active={type === blueType} onClick={() => deployBlue(type)}>
                {type}
              </Chip>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between font-mono text-[10px] text-[#6b6b6b]">
            <span>EST. COST</span>
            <span className="text-white">₹ 3,800 CR</span>
          </div>
          <div className="mt-2 font-mono text-[12px] text-[#1D9E75]">
            −0.3°C TO −1.5°C REDUCTION
          </div>
        </InterventionCard>

        <div className="border-t border-[#1a1a1a] pt-5 mt-5">
          <div className="font-mono text-[10px] text-[#6b6b6b] uppercase">AREA BUDGET UTILIZATION</div>
          <div className="mt-3 h-1.5 w-full rounded-full bg-[#1a1a1a]">
            <div className="h-full w-[11.2%] rounded-full bg-[#F97316]" />
          </div>
          <div className="mt-1 flex justify-between font-mono text-[10px]">
            <span className="text-[#6b6b6b]">11.2% USED</span>
            <span className="text-white">15.0% CAP</span>
          </div>
          <div className="mt-3 text-[#EF4444] font-mono text-[10px]">
            ⚠ BUDGET EXCEEDED
          </div>
        </div>

        {running ? (
          <div className="mt-6 space-y-2 font-mono text-[10px] text-[#6b6b6b]">
            {steps}
          </div>
        ) : (
          <button
            type="button"
            onClick={startOptimization}
            className="mt-6 w-full rounded-none bg-white py-3 text-[11px] font-mono uppercase tracking-wider text-black transition-colors hover:bg-[#F97316] hover:text-white"
          >
            RUN OPTIMIZATION
          </button>
        )}
      </aside>

      <main className="flex-1 px-6 py-6">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">SCENARIO OUTPUT</div>

        {!showResults ? (
          <div className="mt-6 flex h-72 items-center justify-center rounded-xl border border-[#1a1a1a] bg-[#0a0a0a] font-mono text-[11px] text-[#3a3a3a]">
            RUN OPTIMIZATION TO GENERATE COOLED LST MAP
          </div>
        ) : (
          <>
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <ResultPanel label="BASELINE LST" />
              <ResultPanel label="OPTIMIZED LST" />
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="TEMP REDUCTION" value="−2.8°C" valueClass="text-[#1D9E75] text-[28px] font-semibold" />
              <MetricCard label="HOTSPOTS ELIMINATED" value="14 of 22" valueClass="text-white text-[28px] font-semibold" />
              <MetricCard label="AREA TREATED" value="118 km²" valueClass="text-white text-[28px] font-semibold" />
              <MetricCard label="COST EFFICIENCY" value="₹ 4,428 CR/°C" valueClass="text-white text-[20px] font-semibold" />
            </div>

            <div className="mt-4 rounded-xl border border-[#F97316]/30 bg-[#F97316]/5 p-5">
              <div className="font-mono text-[10px] text-[#6b6b6b] uppercase">
                RECOMMENDED STRATEGY — PARETO OPTIMAL
              </div>
              <div className="mt-4 space-y-3 font-mono text-[12px] text-white">
                <div>→ URBAN GREENING · 22% NDVI INCREASE · MIXED TYPOLOGY · ROHINI + OKHLA PRIORITY</div>
                <div>→ COOL ROOFS · ALBEDO 0.65 · 68% BUILDING COVERAGE · INDUSTRIAL ZONES FIRST</div>
                <div>→ BLUE INFRA · 180 HA · DRAINAGE CORRIDOR PLACEMENT · PHASE 2</div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function InterventionCard({
  children,
  disabled,
  className,
}: {
  children: React.ReactNode;
  disabled?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`rounded-none ${className ?? ""} border-t border-[#1a1a1a] pt-5 ${
        disabled ? "opacity-50" : ""
      }`}
    >
      {children}
    </div>
  );
}

function CardHeader({
  title,
  enabled,
  onToggle,
}: {
  title: string;
  enabled: boolean;
  onToggle: (value: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="font-mono text-[11px] text-white">{title}</div>
      <Switch
        checked={enabled}
        onCheckedChange={onToggle}
        className="data-[state=checked]:bg-[#F97316]"
      />
    </div>
  );
}

function CardLabel({ label }: { label: string }) {
  return <div className="mt-3 font-mono text-[10px] text-[#6b6b6b]">{label}</div>;
}

function SliderField({ children, value }: { children: React.ReactNode; value: string }) {
  return (
    <div className="mt-2 space-y-3">
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] text-[#6b6b6b]"> </div>
        <div className="font-mono text-[13px] text-[#F97316]">{value}</div>
      </div>
      {children}
    </div>
  );
}

function Chip({
  children,
  active,
  onClick,
}: {
  children: React.ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2 py-1 text-[10px] font-mono uppercase transition-colors ${
        active ? "border-[#F97316] text-white" : "border-[#2a2a2a] text-[#6b6b6b]"
      }`}
    >
      {children}
    </button>
  );
}

function ResultPanel({ label }: { label: string }) {
  return (
    <div className="flex h-72 items-center justify-center rounded-xl border border-[#1a1a1a] bg-[#0a0a0a] text-center font-mono text-[11px] text-[#3a3a3a]">
      {label}
    </div>
  );
}

function MetricCard({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass: string;
}) {
  return (
    <div className="rounded-xl border border-[#1a1a1a] p-4 bg-[#0a0a0a]">
      <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>
      <div className={valueClass}>{value}</div>
    </div>
  );
}
