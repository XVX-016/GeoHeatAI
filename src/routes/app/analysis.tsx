import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const shapData = [
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
  "NDVI is the dominant cooling signal — each 0.1 unit increase suppresses LST by ~1.4°C in low-albedo zones.",
  "Building density drives 28% of daytime heating via impervious surface radiation trapping.",
  "Sky View Factor controls nocturnal heat retention — high SVF zones show 2.1°C lower night-minimum LST.",
] as const;

const matrixVars = ["LST", "NDVI", "NDBI", "ALBEDO", "BLDG", "SVF"] as const;

const matrixData = [
  ["", "LST", "NDVI", "NDBI", "ALBEDO", "BLDG", "SVF"],
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
  const [activeTab, setActiveTab] = useState<typeof tabLabels[number]>(tabLabels[0]);

  return (
    <div className="px-8 py-8">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">DRIVER ANALYSIS</div>
          <div className="mt-2 font-sans text-[22px] font-semibold text-white">
            Feature attribution & spatial correlation
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          <div className="rounded border border-[#2a2a2a] px-3 py-1.5 font-mono text-[11px] text-white">
            R² 0.87
          </div>
          <div className="rounded border border-[#2a2a2a] px-3 py-1.5 font-mono text-[11px] text-[#F97316]">
            RMSE 1.34°C
          </div>
          <div className="rounded border border-[#2a2a2a] px-3 py-1.5 font-mono text-[11px] text-white">
            SCENES 847
          </div>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-2">
        <div className="border border-[#1a1a1a] p-6">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
            SHAP VALUE ← LST CONTRIBUTION →
          </div>
          <div className="mt-6 h-[280px]">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={shapData}
                margin={{ top: 12, right: 12, bottom: 12, left: 8 }}
              >
                <CartesianGrid stroke="#1a1a1a" vertical={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#6b6b6b", fontSize: 10, fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ fill: "#6b6b6b", fontSize: 10, fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace" }}
                  axisLine={false}
                  tickLine={false}
                  width={120}
                />
                <Tooltip
                  cursor={{ fill: "rgba(255,255,255,0.04)" }}
                  contentStyle={{ backgroundColor: "#0a0a0a", border: "1px solid #1a1a1a", color: "#fff" }}
                  itemStyle={{ color: "#fff" }}
                />
                <Bar dataKey="value" radius={[4, 4, 4, 4]}>
                  {shapData.map((entry) => (
                    <cell key={entry.name} fill={entry.fill} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="mt-6 space-y-3">
            {insights.map((insight, idx) => (
              <div key={idx} className="flex gap-3 border-t border-[#1a1a1a] py-3">
                <div className="font-mono text-[10px] text-[#F97316]">0{idx + 1}</div>
                <div className="font-sans text-[13px] text-[#a0a0a0]">{insight}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="border border-[#1a1a1a] p-6">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">
            PEARSON r — LST vs PREDICTORS
          </div>

          <div className="mt-6 grid grid-cols-7 gap-0 text-center text-[10px]">
            <div className="h-8" />
            {matrixVars.map((header) => (
              <div key={`col-${header}`} className="flex items-center justify-center font-mono text-[9px] uppercase text-[#6b6b6b]">
                {header}
              </div>
            ))}

            {matrixData.slice(1).map((row) => (
              <>
                <div
                  key={`row-${row[0]}`}
                  className="flex items-center justify-center font-mono text-[9px] uppercase text-[#6b6b6b]"
                >
                  {row[0]}
                </div>
                {row.slice(1).map((cellValue, cellIndex) => {
                  if (cellValue === "diag") {
                    return (
                      <div
                        key={`${row[0]}-${cellIndex}`}
                        className="flex aspect-square items-center justify-center bg-[#1a1a1a] font-mono text-[10px] text-white"
                      >
                        —
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
              </>
            ))}
          </div>
        </div>
      </div>

      <div className="border border-[#1a1a1a] mt-6 p-6">
        <div className="flex flex-wrap gap-3 border-b border-[#1a1a1a] pb-4">
          {tabLabels.map((label) => {
            const active = activeTab === label;
            return (
              <button
                key={label}
                type="button"
                onClick={() => setActiveTab(label)}
                className={`font-mono text-[10px] uppercase transition-colors ${
                  active ? "text-white border-b-2 border-[#F97316]" : "text-[#6b6b6b]"
                } pb-2`}
              >
                {label}
              </button>
            );
          })}
        </div>

        <div className="mt-6 bg-[#0a0a0a] h-48 flex items-center justify-center font-mono text-[11px] text-[#3a3a3a]">
          CHOROPLETH MAP — DELHI ADMINISTRATIVE ZONES
        </div>
      </div>
    </div>
  );
}
