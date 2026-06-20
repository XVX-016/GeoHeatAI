import {
  CartesianGrid,
  Line,
  ReferenceDot,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export type ParetoPoint = {
  id: number;
  cost: number;
  dt: number;
  equity: number;
};

export default function ParetoScatterChart({
  data,
  recommended,
  selectedPoint,
  onPointClick,
}: {
  data: ParetoPoint[];
  recommended?: ParetoPoint;
  selectedPoint?: ParetoPoint;
  onPointClick: (id: number) => void;
}) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ScatterChart margin={{ top: 10, right: 20, left: 60, bottom: 50 }}>
        <CartesianGrid stroke="#1a1a1a" />
        <XAxis
          dataKey="cost"
          name="Cost"
          type="number"
          tick={{ fill: "#a0a0a0", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          label={{
            value: "Implementation cost (₹ CR)",
            position: "insideBottom",
            offset: -10,
            fill: "#a0a0a0",
            style: { fontFamily: "JetBrains Mono, monospace", fontSize: 10 },
          }}
        />
        <YAxis
          dataKey="dt"
          name="ΔT"
          type="number"
          tick={{ fill: "#a0a0a0", fontSize: 10 }}
          axisLine={false}
          tickLine={false}
          label={{
            value: "Temperature reduction (ΔT °C)",
            angle: -90,
            position: "insideLeft",
            fill: "#a0a0a0",
            style: { fontFamily: "JetBrains Mono, monospace", fontSize: 10 },
            offset: 10,
          }}
        />
        <Tooltip
          cursor={{ stroke: "#1a1a1a" }}
          contentStyle={{ background: "#0a0a0a", border: "1px solid #1a1a1a", color: "#fff" }}
        />

        <Line
          type="monotone"
          dataKey="dt"
          data={data}
          stroke="#2a2a2a"
          strokeWidth={1}
          strokeDasharray="4 4"
          dot={false}
          isAnimationActive={false}
        />

        <Scatter
          name="Pareto solutions"
          data={data}
          fill="#F97316"
          fillOpacity={0.4}
          onClick={(props) => {
            const payload = (props as { payload?: ParetoPoint }).payload;
            if (payload) onPointClick(payload.id);
          }}
        />

        {recommended && (
          <ReferenceDot
            x={recommended.cost}
            y={recommended.dt}
            r={6}
            fill="#F97316"
            fillOpacity={1}
            stroke="#F97316"
            strokeWidth={2}
          />
        )}

        {selectedPoint && (
          <ReferenceDot
            x={selectedPoint.cost}
            y={selectedPoint.dt}
            r={5}
            fill="none"
            stroke="#F97316"
            strokeWidth={2}
            strokeDasharray="4 4"
          />
        )}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
