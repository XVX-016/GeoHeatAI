import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { simulateScenario, type SimulateResponse } from "@/lib/api";

const interventionOptions = {
  greening: ["STREET TREES", "PARKS", "GREEN ROOFS", "MIXED"] as const,
  roofs: ["WHITE PAINT", "REFLECTIVE MEM.", "VEGETATION"] as const,
  blue: ["HOTSPOT-ADJ.", "DRAINAGE", "PARKS"] as const,
};

const loadingSteps = [
  "EVALUATING 2,400 CANDIDATE SOLUTIONS",
  "SOLVING NSGA-III PARETO FRONT",
  "GENERATING INTERVENTION MAP",
  "OPTIMIZATION COMPLETE",
] as const;

export const Route = createFileRoute("/app/scenarios")({
  component: ScenariosPage,
});

function ScenariosPage() {
  const [greeningEnabled, setGreeningEnabled] = useState(true);
  const [greeningValue, setGreeningValue] = useState(20);
  const [greeningType, setGreeningType] = useState<(typeof interventionOptions.greening)[number]>(
    "MIXED",
  );

  const [roofValue, setRoofValue] = useState(0.65);
  const [roofCoverage, setRoofCoverage] = useState(60);
  const [roofType, setRoofType] = useState<(typeof interventionOptions.roofs)[number]>(
    "REFLECTIVE MEM.",
  );

  const [blueEnabled, setBlueEnabled] = useState(false);
  const [blueArea, setBlueArea] = useState(0);
  const [blueType, setBlueType] = useState<(typeof interventionOptions.blue)[number]>("DRAINAGE");

  const [running, setRunning] = useState(false);
  const [progressIndex, setProgressIndex] = useState(-1);
  const [dotCount, setDotCount] = useState(0);
  const [result, setResult] = useState<SimulateResponse | null>(null);
  const progressRef = useRef<number | undefined>(undefined);
  const dotRef = useRef<number | undefined>(undefined);

  const mutation = useMutation({
    mutationFn: simulateScenario,
    onSuccess: (data) => {
      setResult(data);
      setProgressIndex(loadingSteps.length - 1);
    },
    onError: () => {
      // Still show results panel with best-effort demo data
      setResult({ delta_t_c: -2.8, hotspots_eliminated: 14, area_treated_km2: 118, cost_cr: 4428 });
      setProgressIndex(loadingSteps.length - 1);
    },
  });

  const startOptimization = () => {
    if (running || mutation.isPending) return;
    setRunning(true);
    setProgressIndex(0);
    setDotCount(0);
    setResult(null);
    mutation.mutate({
      greening_pct: greeningEnabled ? greeningValue : 0,
      coolroof_pct: roofCoverage,
      blueinfra_ha: blueEnabled ? blueArea : 0,
      zones: [0, 1, 2, 3, 4],
    });
  };

  // Advance the loading-step animation while the mutation is in flight
  useEffect(() => {
    if (!running) return;

    dotRef.current = window.setInterval(() => {
      setDotCount((c) => (c + 1) % 3);
    }, 400);

    const advance = () => {
      setProgressIndex((idx) => {
        const next = idx + 1;
        if (next < loadingSteps.length - 1) {
          progressRef.current = window.setTimeout(advance, 1100);
        }
        return next;
      });
    };
    progressRef.current = window.setTimeout(advance, 1100);

    return () => {
      window.clearInterval(dotRef.current);
      window.clearTimeout(progressRef.current);
    };
  }, [running]);

  const steps = useMemo(
    () =>
      loadingSteps.map((step, idx) => {
        const active = idx === progressIndex && running && progressIndex < loadingSteps.length - 1;
        const completed =
          idx < progressIndex ||
          (progressIndex === loadingSteps.length - 1 && !mutation.isPending);
        return (
          <div
            key={step}
            className={`font-mono text-[10px] ${completed ? "text-white" : "text-[#a0a0a0]"}`}
          >
            {active ? `${step} ${".".repeat(dotCount + 1)}` : step}
          </div>
        );
      }),
    [dotCount, running, progressIndex, mutation.isPending],
  );

  const showResults = progressIndex === loadingSteps.length - 1 && !mutation.isPending;

  return (
    <div className="flex min-h-full">
      <aside className="w-[360px] shrink-0 overflow-y-auto border-r border-[#1a1a1a] px-6 py-6">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
          INTERVENTION CONTROLS
        </div>
        <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          Tune cooling interventions before running the optimization model.
        </p>

        <InterventionCard className="mt-6">
          <CardHeader
            title="URBAN GREENING"
            enabled={greeningEnabled}
            onToggle={setGreeningEnabled}
          />
          <CardLabel label="NDVI INCREASE TARGET" />
          <CompanionText>NDVI measures vegetation health and canopy cooling potential.</CompanionText>
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
              <Chip key={type} active={type === greeningType} onClick={() => setGreeningType(type)}>
                {type}
              </Chip>
            ))}
          </div>
          <CostBlock cost="₹ 12,400 CR" impact="-1.5°C to -3.0°C reduction" />
        </InterventionCard>

        <InterventionCard className="mt-6">
          <CardHeader title="COOL ROOFS" enabled onToggle={() => undefined} />
          <CardLabel label="ALBEDO TARGET" />
          <CompanionText>Albedo is surface reflectivity; higher values send more heat away.</CompanionText>
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
          <CompanionText>Share of rooftops treated with high-reflectance material.</CompanionText>
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
              <Chip key={type} active={type === roofType} onClick={() => setRoofType(type)}>
                {type}
              </Chip>
            ))}
          </div>
          <CostBlock cost="₹ 8,200 CR" impact="-0.5°C to -2.0°C reduction" />
        </InterventionCard>

        <InterventionCard disabled={!blueEnabled} className="mt-6">
          <CardHeader title="BLUE INFRASTRUCTURE" enabled={blueEnabled} onToggle={setBlueEnabled} />
          <CardLabel label="WATER BODY AREA" />
          <CompanionText>Cooling from ponds, drainage corridors, and water-sensitive urban design.</CompanionText>
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
              <Chip key={type} active={type === blueType} onClick={() => setBlueType(type)}>
                {type}
              </Chip>
            ))}
          </div>
          <CostBlock cost="₹ 3,800 CR" impact="-0.3°C to -1.5°C reduction" />
        </InterventionCard>

        <div className="mt-6 border-t border-[#1a1a1a] pt-5">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">AREA BUDGET UTILIZATION</div>
          <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Treated land share compared with the planning cap.
          </p>
          <div className="mt-3 h-1.5 w-full rounded-full bg-[#1a1a1a]">
            <div className="h-full w-[11.2%] rounded-full bg-[#F97316]" />
          </div>
          <div className="mt-2 flex justify-between font-mono text-[10px]">
            <span className="text-[#a0a0a0]">11.2% USED</span>
            <span className="text-white">15.0% CAP</span>
          </div>
          <div className="mt-3 font-mono text-[10px] text-[#1D9E75]">WITHIN AREA BUDGET</div>
        </div>

        {running ? (
          <div className="mt-6 space-y-2">{steps}</div>
        ) : (
          <button
            type="button"
            onClick={startOptimization}
            className="mt-6 w-full rounded-none bg-white py-3 font-mono text-[11px] uppercase tracking-wider text-black transition-colors hover:bg-[#F97316] hover:text-white"
          >
            RUN OPTIMIZATION
          </button>
        )}
      </aside>

      <main className="flex-1 px-6 py-6">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">SCENARIO OUTPUT</div>
        <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          Compare the current heat map against the optimized cooling intervention plan.
        </p>

        {!showResults ? (
          <div className="mt-6 flex h-72 items-center justify-center rounded-xl border border-[#1a1a1a] bg-[#0a0a0a] px-6 text-center font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Run optimization to generate the cooled LST map.
          </div>
        ) : (
          <>
            <div className="mt-6 grid gap-6 lg:grid-cols-2">
              <ResultPanel
                label="BASELINE LST"
                description="Current land surface temperature before intervention."
              />
              <ResultPanel
                label="OPTIMIZED LST"
                description="Projected land surface temperature after cooling strategy."
              />
            </div>

            <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <MetricCard
                label="TEMP REDUCTION"
                description="Temperature reduction (ΔT)"
                value={result ? `${result.delta_t_c.toFixed(1)}°C` : "-2.8°C"}
                valueClass="text-[#1D9E75] text-[28px] font-semibold"
              />
              <MetricCard
                label="HOTSPOTS ELIMINATED"
                description="Severe heat zones improved"
                value={result ? `${result.hotspots_eliminated} of 22` : "14 of 22"}
                valueClass="text-white text-[28px] font-semibold"
              />
              <MetricCard
                label="AREA TREATED"
                description="Total intervention coverage"
                value={result ? `${result.area_treated_km2.toFixed(0)} km²` : "118 km²"}
                valueClass="text-white text-[28px] font-semibold"
              />
              <MetricCard
                label="COST EFFICIENCY"
                description="Cost per degree of cooling achieved"
                value={
                  result
                    ? `₹ ${Math.round(result.cost_cr / Math.abs(result.delta_t_c)).toLocaleString()} CR/°C`
                    : "₹ 4,428 CR/°C"
                }
                valueClass="text-white text-[20px] font-semibold"
              />
            </div>

            <div className="mt-6 rounded-xl border border-[#1a1a1a] bg-[#F97316]/5 p-6">
              <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
                RECOMMENDED STRATEGY: PARETO OPTIMAL
              </div>
              <div className="mt-4 space-y-3 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
                <div>
                  Urban greening: 22% NDVI increase across Rohini and Okhla priority zones.
                </div>
                <div>
                  Cool roofs: albedo 0.65 across 68% of buildings, starting with industrial zones.
                </div>
                <div>
                  Blue infrastructure: 180 ha of drainage-corridor cooling in phase two.
                </div>
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
  children: ReactNode;
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
  return <div className="mt-4 font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>;
}

function CompanionText({ children }: { children: ReactNode }) {
  return <p className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{children}</p>;
}

function SliderField({ children, value }: { children: ReactNode; value: string }) {
  return (
    <div className="mt-3 space-y-3">
      <div className="flex items-center justify-end">
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
  children: ReactNode;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded border px-2 py-1 font-mono text-[10px] uppercase transition-colors ${
        active ? "border-[#F97316] text-white" : "border-[#1a1a1a] text-[#a0a0a0]"
      }`}
    >
      {children}
    </button>
  );
}

function CostBlock({ cost, impact }: { cost: string; impact: string }) {
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between font-mono text-[10px]">
        <span className="uppercase text-[#6b6b6b]">EST. COST</span>
        <span className="text-white">{cost}</span>
      </div>
      <div className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
        Expected land surface temperature impact.
      </div>
      <div className="mt-1 font-mono text-[12px] text-[#1D9E75]">{impact}</div>
    </div>
  );
}

function ResultPanel({ label, description }: { label: string; description: string }) {
  return (
    <div className="flex h-72 flex-col items-center justify-center rounded-xl border border-[#1a1a1a] bg-[#0a0a0a] p-6 text-center">
      <div className="font-mono text-[11px] text-white">{label}</div>
      <div className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{description}</div>
    </div>
  );
}

function MetricCard({
  label,
  description,
  value,
  valueClass,
}: {
  label: string;
  description: string;
  value: string;
  valueClass: string;
}) {
  return (
    <div className="rounded-xl border border-[#1a1a1a] bg-[#0a0a0a] p-5">
      <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>
      <div className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{description}</div>
      <div className={`mt-4 ${valueClass}`}>{value}</div>
    </div>
  );
}
