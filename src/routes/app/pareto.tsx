import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/app/pareto")({
  component: ParetoPage,
});

function ParetoPage() {
  return (
    <div className="flex min-h-full items-center justify-center text-[#6b6b6b] font-mono text-[11px] uppercase">
      PARETO
    </div>
  );
}
