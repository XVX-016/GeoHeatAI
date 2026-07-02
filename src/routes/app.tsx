import { createFileRoute, Link, Outlet, useRouterState } from "@tanstack/react-router";
import { BarChart3, Download, GitBranch, Layers, SlidersHorizontal } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

const APP_NAV = [
  { label: "MAP", to: "/app/map", Icon: Layers },
  { label: "ANALYSIS", to: "/app/analysis", Icon: BarChart3 },
  { label: "SCENARIOS", to: "/app/scenarios", Icon: SlidersHorizontal },
  { label: "PARETO", to: "/app/pareto", Icon: GitBranch },
  { label: "EXPORT", to: "/app/export", Icon: Download },
] as const;

export const Route = createFileRoute("/app")({
  component: AppShell,
});

function AppShell() {
  const pathname = useRouterState({
    select: (state) => state.location.pathname,
  });
  const currentPage = APP_NAV.find((item) => pathname === item.to)?.label || "MAP";

  const { data: healthData } = useQuery({
    queryKey: ["health"],
    queryFn: api.health,
    retry: false,
    refetchInterval: 30_000,
    staleTime: 25_000,
  });

  const backendOnline = !!healthData;

  return (
    <div className="min-h-screen bg-black text-white">
      <aside className="fixed inset-y-0 left-0 flex w-[240px] flex-col border-r border-[#1a1a1a] bg-black text-white">
        <div className="px-6 py-5">
          <div className="flex items-center gap-2 font-sans text-[15px] font-semibold">
            <span className="lowercase">
              geoheat<span className="text-[#F97316]">AI</span>
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-[#F97316]" aria-hidden />
          </div>
        </div>

        <nav className="flex-1 space-y-2 px-2 py-5">
          {APP_NAV.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              activeOptions={{ exact: true }}
              className="flex items-center gap-3 rounded-r-full px-4 py-3 font-mono text-[11px] uppercase tracking-wide transition-colors"
              activeProps={{
                className: "border-l-2 border-[#F97316] bg-white/5 text-white",
              }}
              inactiveProps={{
                className: "text-[#a0a0a0] hover:text-white",
              }}
            >
              <item.Icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="px-6 pb-6 pt-5">
          <div className="font-mono text-[10px] uppercase text-[#6b6b6b]">MODEL</div>
          <div className="mt-1 font-sans text-[12px] leading-[1.7] text-[#a0a0a0]">
            Physics-informed + XGBoost ensemble
          </div>
          <div className="mt-3 font-mono text-[10px] uppercase text-[#6b6b6b]">CITY</div>
          <div className="mt-1 font-sans text-[12px] leading-[1.7] text-white">Delhi NCR</div>
        </div>
      </aside>

      <div className="ml-[240px] min-h-screen bg-black">
        <header className="flex h-12 items-center justify-between border-b border-[#1a1a1a] px-6">
          <div className="font-mono text-[11px] uppercase text-[#6b6b6b]">{currentPage}</div>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase text-white">
            <span
              className={`h-2 w-2 rounded-full transition-colors ${
                backendOnline ? "bg-emerald-400" : "bg-yellow-400"
              }`}
              aria-hidden
            />
            {backendOnline ? "PIPELINE READY" : "BACKEND OFFLINE"}
          </div>
        </header>

        <main className="min-h-[calc(100vh-3rem)] bg-black px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
