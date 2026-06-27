import { lazy, Suspense, useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { getDrivers } from "@/lib/api";

const ShapBarChart = lazy(() => import("@/components/ShapBarChart"));

// Static fallback used when the backend is offline
const STATIC_SHAP = [
  { name: "NDVI", value: -0.34, fill: "#1D9E75" },
  { name: "Building density", value: 0.28, fill: "#F97316" },
  { name: "Albedo", value: -0.22, fill: "#1D9E75" },
  { name: "Air temp", value: 0.19, fill: "#F97316" },
  { name: "SVF", value: 0.16, fill: "#F97316" },
  { name: "Impervious", value: 0.14, fill: "#F97316" },
  { name: "Wind", value: -0.09, fill: "#1D9E75" },
  { name: "Humidity", value: -0.07, fill: "#1D9E75" },
] as const;

const insights = [
  "NDVI is the dominant cooling signal; each 0.1 unit increase suppresses LST by about 1.4°C in low-albedo zones.",
  "Building density drives 28% of daytime heating through impervious surface radiation trapping.",
  "Sky View Factor (SVF) controls nocturnal heat retention; high SVF zones show 2.1°C lower night-minimum LST.",
] as const;

const matrixVars = ["LST", "NDVI", "NDBI", "ALBEDO", "BLDG", "SVF"] as const;

const matrixDescriptions: Record<(typeof matrixVars)[number], string> = {
  LST: "Land surface temperature",
  NDVI: "Vegetation health index",
  NDBI: "Built-up surface index",
  ALBEDO: "Surface reflectivity",
  BLDG: "Building density",
  SVF: "Sky View Factor",
};

const matrixData = [
  ["LST", "diag", "-0.72", "0.68", "-0.61", "0.54", "0.47"],
  ["NDVI", "-0.72", "diag", "-0.38", "0.21", "-0.49", "0.12"],
  ["NDBI", "0.68", "-0.38", "diag", "0.44", "0.61", "-0.15"],
  ["ALBEDO", "-0.61", "0.21", "0.44", "diag", "0.28", "-0.04"],
  ["BLDG", "0.54", "-0.49", "0.61", "0.28", "diag", "-0.09"],
  ["SVF", "0.47", "0.12", "-0.15", "-0.04", "-0.09", "diag"],
] as const;

const tabLabels = ["NDVI DEFICIT", "BUILDING DENSITY", "ALBEDO", "SKY VIEW FACTOR"] as const;

export const Route = createFileRoute("/app/analysis")({
  component: AnalysisPage,
});

function AnalysisPage() {
  const [activeTab, setActiveTab] = useState<(typeof tabLabels)[number]>(tabLabels[0]);

  const { data: driversData, isLoading: driversLoading, isError: driversError } = useQuery({
    queryKey: ["drivers"],
    queryFn: getDrivers,
    retry: 1,
    staleTime: 60_000,
  });

  // Build chart data from API if available, else fall back to static data
  const shapData = driversData
    ? driversData.feature_names.map((name, i) => {
        const val = driversData.mean_abs_shap[i];
        // Use sign from static data where name matches, else positive = heating
        const staticMatch = STATIC_SHAP.find(
          (s) => s.name.toLowerCase() === name.toLowerCase(),
        );
        const signed = staticMatch ? Math.sign(staticMatch.value) * val : val;
        return {
          name,
          value: Number(signed.toFixed(4)),
          fill: signed < 0 ? "#1D9E75" : "#F97316",
        };
      })
    : STATIC_SHAP;

  // Top-3 driver text lines
  const insightLines: readonly string[] = driversData?.top_3_drivers.map(
    (d, i) =>
      `[${i + 1}] ${d.feature}: mean |SHAP| = ${d.mean_abs_shap_value.toFixed(3)}°C average impact on LST`,
  ) ?? insights;

  return (
    <div className="px-8 py-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">DRIVER ANALYSIS</div>
          <div className="mt-3 font-sans text-[22px] font-semibold text-white">
            Feature attribution & spatial correlation
          </div>
          <p className="mt-2 max-w-2xl font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            SHAP explains which urban features push land surface temperature higher or lower.
          </p>
        </div>

        <div className="flex flex-wrap gap-3">
          <MetricBadge label="R²" description="Model fit" value="0.87" />
          <MetricBadge label="RMSE" description="Average error" value="1.34°C" highlight />
          <MetricBadge label="SCENES" description="Cloud-masked satellite images" value="847" />
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-2">
        <div className="border border-[#1a1a1a] p-6">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
            SHAP VALUE: LST CONTRIBUTION
          </div>
          <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Teal bars indicate cooling influence; orange bars indicate heating influence.
          </p>
        <div className="mt-6 h-[280px]">
            {driversLoading ? (
              <div className="flex h-full animate-pulse items-center justify-center bg-[#0a0a0a] font-mono text-[10px] uppercase text-[#6b6b6b]">
                LOADING SHAP DATA...
              </div>
            ) : driversError ? (
              <div className="flex h-full flex-col items-center justify-center gap-2 bg-[#0a0a0a]">
                <div className="font-mono text-[10px] text-yellow-500">BACKEND OFFLINE — SHOWING DEMO DATA</div>
                <Suspense fallback={<ChartFallback label="Loading SHAP chart" />}>
                  <ShapBarChart data={shapData as { name: string; value: number; fill: string }[]} />
                </Suspense>
              </div>
            ) : (
              <Suspense fallback={<ChartFallback label="Loading SHAP chart" />}>
                <ShapBarChart data={shapData as { name: string; value: number; fill: string }[]} />
              </Suspense>
            )}
          </div>

          <div className="mt-6 space-y-3">
            {insightLines.map((insight, idx) => (
              <div key={idx} className="flex gap-3 border-t border-[#1a1a1a] py-4">
                <div className="font-mono text-[10px] text-[#F97316]">0{idx + 1}</div>
                <div className="font-sans text-[13px] leading-[1.7] text-[#a0a0a0]">{insight}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-[#1a1a1a] p-6">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
            PEARSON R: LST VS PREDICTORS
          </div>
          <p className="mt-2 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Correlation shows which variables rise or fall together with surface heat.
          </p>

          <div className="mt-6 grid grid-cols-7 gap-0 text-center text-[10px]">
            <div className="h-10" />
            {matrixVars.map((header) => (
              <div key={`col-${header}`} className="flex flex-col items-center justify-center">
                <span className="font-mono text-[9px] uppercase text-[#6b6b6b]">{header}</span>
                <span className="mt-1 max-w-[72px] font-sans text-[10px] leading-tight text-[#a0a0a0]">
                  {matrixDescriptions[header]}
                </span>
              </div>
            ))}

            {matrixData.map((row) => (
              <div key={`row-group-${row[0]}`} className="contents">
                <div className="flex flex-col items-center justify-center px-1">
                  <span className="font-mono text-[9px] uppercase text-[#6b6b6b]">{row[0]}</span>
                  <span className="mt-1 font-sans text-[10px] leading-tight text-[#a0a0a0]">
                    {matrixDescriptions[row[0] as (typeof matrixVars)[number]]}
                  </span>
                </div>
                {row.slice(1).map((cellValue, cellIndex) => {
                  if (cellValue === "diag") {
                    return (
                      <div
                        key={`${row[0]}-${cellIndex}`}
                        className="flex aspect-square items-center justify-center bg-[#1a1a1a] font-mono text-[10px] text-white"
                      >
                        -
                      </div>
                    );
                  }

                  const value = Number(cellValue);
                  const positive = value > 0;
                  const magnitude = Math.abs(value);
                  const opacityClass =
                    magnitude >= 0.7
                      ? "bg-opacity-[0.72]"
                      : magnitude >= 0.5
                        ? "bg-opacity-[0.56]"
                        : magnitude >= 0.3
                          ? "bg-opacity-[0.42]"
                          : "bg-opacity-[0.28]";
                  const colorClass = positive ? "bg-[#F97316]" : "bg-[#1D9E75]";
                  return (
                    <div
                      key={`${row[0]}-${cellIndex}`}
                      className={`flex aspect-square items-center justify-center font-mono text-[10px] text-white ${colorClass} ${opacityClass}`}
                    >
                      {cellValue}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-6 border border-[#1a1a1a] p-6">
        <div className="flex flex-wrap gap-3 border-b border-[#1a1a1a] pb-4">
          {tabLabels.map((label) => {
            const active = activeTab === label;
            return (
              <button
                key={label}
                type="button"
                onClick={() => setActiveTab(label)}
                className={`pb-2 font-mono text-[10px] uppercase transition-colors ${
                  active ? "border-b-2 border-[#F97316] text-white" : "text-[#a0a0a0]"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="mt-6 flex h-48 items-center justify-center bg-[#0a0a0a] font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
          Choropleth map: Delhi administrative zones colored by the selected heat driver.
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

function MetricBadge({
  label,
  description,
  value,
  highlight,
}: {
  label: string;
  description: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="rounded border border-[#1a1a1a] px-3 py-2">
      <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">{label}</div>
      <div className={`mt-1 font-mono text-[11px] ${highlight ? "text-[#F97316]" : "text-white"}`}>
        {value}
      </div>
      <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">{description}</div>
    </div>
  );
}
