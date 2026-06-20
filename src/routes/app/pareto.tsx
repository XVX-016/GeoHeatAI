import { lazy, Suspense, useMemo, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Slider } from "@/components/ui/slider";
import type { ParetoPoint } from "@/components/ParetoScatterChart";

const ParetoScatterChart = lazy(() => import("@/components/ParetoScatterChart"));

type ScenarioRow = {
  id: string;
  greening: number;
  roof: number;
  blue: number;
  dt: string;
  cost: string;
  equity: string;
};

const SAMPLE_ROWS: ScenarioRow[] = [
  { id: "P-01", greening: 22, roof: 68, blue: 180, dt: "-2.8°C", cost: "₹ 4,428", equity: "0.82" },
  { id: "P-02", greening: 18, roof: 60, blue: 120, dt: "-2.3°C", cost: "₹ 3,920", equity: "0.79" },
  { id: "P-03", greening: 26, roof: 72, blue: 200, dt: "-3.0°C", cost: "₹ 5,120", equity: "0.85" },
  { id: "P-04", greening: 12, roof: 40, blue: 40, dt: "-1.1°C", cost: "₹ 1,820", equity: "0.61" },
  { id: "P-05", greening: 30, roof: 80, blue: 260, dt: "-3.4°C", cost: "₹ 6,240", equity: "0.89" },
  { id: "P-06", greening: 8, roof: 32, blue: 20, dt: "-0.7°C", cost: "₹ 980", equity: "0.45" },
  { id: "P-07", greening: 16, roof: 55, blue: 90, dt: "-1.9°C", cost: "₹ 2,680", equity: "0.72" },
  { id: "P-08", greening: 20, roof: 60, blue: 110, dt: "-2.0°C", cost: "₹ 3,200", equity: "0.76" },
];

export const Route = createFileRoute("/app/pareto")({
  component: ParetoPage,
});

function randomPareto(n = 40): ParetoPoint[] {
  const points: ParetoPoint[] = [];
  for (let i = 0; i < n; i++) {
    const cost = Math.round(100 + Math.random() * 4900);
    const dt = Number((0.2 + Math.random() * 3.8).toFixed(2));
    const equity = Number((0.2 + Math.random() * 0.8).toFixed(2));
    points.push({ id: i + 1, cost, dt, equity });
  }
  points.sort((a, b) => a.cost - b.cost);
  return points;
}

function ParetoPage() {
  const [weights, setWeights] = useState({ cost: 0.33, temp: 0.33, equity: 0.34 });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const data = useMemo(() => randomPareto(40), []);
  const recommended = useMemo(() => data[8], [data]);
  const selectedPoint = useMemo(
    () => data.find((point) => point.id === selectedId),
    [data, selectedId],
  );

  const handlePointClick = (id: number) => {
    setSelectedId(id);
  };

  return (
    <div className="px-8 py-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">PARETO EXPLORER</div>
          <div className="mt-3 font-sans text-[22px] font-semibold text-white">
            Multi-objective optimization front
          </div>
          <p className="mt-2 max-w-2xl font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Compare intervention plans that balance cost, cooling, and equitable benefit.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <SummaryBadge label="SOLUTIONS" value="2,400" description="Candidate plans tested" />
          <SummaryBadge label="PARETO FRONT" value="47" description="Best tradeoff solutions" />
          <SummaryBadge label="OBJECTIVES" value="3" description="Cost, cooling, equity" />
        </div>
      </div>

      <div className="mt-6 border border-[#1a1a1a] p-6">
        <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
          COST VS ΔT VS EQUITY: NSGA-III PARETO FRONT
        </div>
        <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          NSGA-III searches for plans where no objective can improve without compromising another.
        </p>
        <div className="relative mt-6 h-[320px]">
          <Suspense fallback={<ChartFallback label="Loading Pareto chart" />}>
            <ParetoScatterChart
              data={data}
              recommended={recommended}
              selectedPoint={selectedPoint}
              onPointClick={handlePointClick}
            />
          </Suspense>

          {recommended && (
            <div className="pointer-events-none absolute left-4 top-4 flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-[#F97316]" />
              <div className="font-mono text-[10px] text-[#F97316]">RECOMMENDED TRADEOFF</div>
            </div>
          )}
        </div>

        <div className="mt-6">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">REWEIGHT OBJECTIVES</div>
          <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Adjust the importance of cost, temperature reduction, and equity distribution.
          </p>
          <div className="mt-4 space-y-4">
            <WeightSlider
              label="COST MINIMIZATION"
              description="Lower capital cost for implementation."
              value={weights.cost}
              onChange={(v) => setWeights((w) => ({ ...w, cost: v }))}
            />
            <WeightSlider
              label="TEMPERATURE REDUCTION"
              description="Projected cooling measured as ΔT."
              value={weights.temp}
              onChange={(v) => setWeights((w) => ({ ...w, temp: v }))}
            />
            <WeightSlider
              label="EQUITY DISTRIBUTION"
              description="Cooling benefits reaching heat-vulnerable communities."
              value={weights.equity}
              onChange={(v) => setWeights((w) => ({ ...w, equity: v }))}
            />
          </div>
        </div>

        <div className="mt-6">
          <div className="overflow-x-auto">
            <table className="w-full table-fixed border-collapse">
              <thead className="bg-[#0a0a0a]">
                <tr className="border-b border-[#1a1a1a]">
                  <TableHead label="ID" description="Plan" alignLeft />
                  <TableHead label="GREENING %" description="NDVI gain" />
                  <TableHead label="COOL ROOF %" description="Roof coverage" />
                  <TableHead label="BLUE INFRA HA" description="Water cooling area" />
                  <TableHead label="ΔT °C" description="Temperature reduction" />
                  <TableHead label="COST ₹CR" description="Capital cost" />
                  <TableHead label="EQUITY" description="Benefit distribution" />
                </tr>
              </thead>
              <tbody className="font-mono text-[11px] text-[#a0a0a0]">
                {SAMPLE_ROWS.map((row, index) => (
                  <tr
                    key={row.id}
                    className={`cursor-pointer border-b border-[#1a1a1a] transition-colors hover:bg-[#0a0a0a] ${
                      index === 2 ? "border-l-2 border-[#F97316] bg-[#F97316]/5 text-white" : ""
                    }`}
                    onClick={() => handlePointClick(index + 1)}
                  >
                    <td className="p-3">{row.id}</td>
                    <td className="p-3">{row.greening}%</td>
                    <td className="p-3">{row.roof}%</td>
                    <td className="p-3">{row.blue}</td>
                    <td className="p-3">{row.dt}</td>
                    <td className="p-3">{row.cost}</td>
                    <td className="p-3">{row.equity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChartFallback({ label }: { label: string }) {
  return (
    <div className="flex h-full items-center justify-center bg-[#0a0a0a] font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
      {label}
    </div>
  );
}

function SummaryBadge({
  label,
  value,
  description,
}: {
  label: string;
  value: string;
  description: string;
}) {
  return (
    <div className="rounded border border-[#1a1a1a] px-3 py-2">
      <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>
      <div className="mt-1 font-mono text-[11px] text-white">{value}</div>
      <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{description}</div>
    </div>
  );
}

function WeightSlider({
  label,
  description,
  value,
  onChange,
}: {
  label: string;
  description: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>
          <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            {description}
          </div>
        </div>
        <div className="font-mono text-[12px] text-[#F97316]">{Math.round(value * 100)}%</div>
      </div>
      <Slider
        value={[Math.round(value * 100)]}
        min={0}
        max={100}
        step={1}
        onValueChange={([v]) => onChange(v / 100)}
        className="mt-3 h-6"
      >
        <Slider.Track className="relative h-1.5 w-full overflow-hidden rounded-full bg-[#1a1a1a]">
          <Slider.Range className="absolute h-full bg-[#F97316]" />
        </Slider.Track>
        <Slider.Thumb className="block h-4 w-4 rounded-full border border-white bg-white shadow transition-colors focus-visible:outline-none" />
      </Slider>
    </div>
  );
}

function TableHead({
  label,
  description,
  alignLeft,
}: {
  label: string;
  description: string;
  alignLeft?: boolean;
}) {
  return (
    <th className={`p-3 ${alignLeft ? "text-left" : ""}`}>
      <div className="font-mono text-[9px] uppercase text-[#6b6b6b]">{label}</div>
      <div className="mt-1 font-sans text-[10px] leading-tight text-[#a0a0a0]">{description}</div>
    </th>
  );
}
