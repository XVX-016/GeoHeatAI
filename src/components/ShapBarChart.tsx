import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type ShapDatum = {
  name: string;
  value: number;
  fill: string;
};

export default function ShapBarChart({ data }: { data: ShapDatum[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart layout="vertical" data={data} margin={{ top: 12, right: 12, bottom: 12, left: 8 }}>
        <CartesianGrid stroke="#1a1a1a" vertical={false} />
        <XAxis
          type="number"
          tick={{
            fill: "#a0a0a0",
            fontSize: 10,
            fontFamily:
              "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          tick={{
            fill: "#a0a0a0",
            fontSize: 10,
            fontFamily:
              "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          }}
          axisLine={false}
          tickLine={false}
          width={120}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.04)" }}
          contentStyle={{
            backgroundColor: "#0a0a0a",
            border: "1px solid #1a1a1a",
            color: "#fff",
          }}
          itemStyle={{ color: "#fff" }}
        />
        <Bar dataKey="value" radius={[4, 4, 4, 4]}>
          {data.map((entry) => (
            <Cell key={entry.name} fill={entry.fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
