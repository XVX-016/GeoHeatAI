import { createFileRoute, Outlet, useRouter } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { BarChart3, Download, GitBranch, Layers, SlidersHorizontal } from "lucide-react";

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
  const router = useRouter();
  const pathname = router.state.location.pathname || "/app/map";
  const currentPage = APP_NAV.find((item) => pathname === item.to)?.label || "MAP";

  return (
    <div className="min-h-screen bg-black text-white">
      <aside className="fixed inset-y-0 left-0 w-[240px] border-r border-[#1a1a1a] bg-black text-white flex flex-col">
        <div className="px-6 py-5">
          <div className="flex items-center gap-2 font-sans text-[15px] font-semibold">
            <span className="lowercase">
              geoheat<span className="text-[#F97316]">AI</span>
            </span>
            <span className="h-1.5 w-1.5 rounded-full bg-[#F97316]" aria-hidden />
          </div>
        </div>

        <nav className="flex-1 px-2 py-4 space-y-1">
          {APP_NAV.map((item) => {
            const isActive = pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 rounded-r-full px-4 py-3 text-[11px] uppercase tracking-wide font-mono transition-colors ${
                  isActive
                    ? "text-white border-l-2 border-[#F97316] bg-white/5"
                    : "text-[#6b6b6b] hover:text-white"
                }`}
              >
                <item.Icon className="h-4 w-4" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-6 pb-6 pt-5 font-mono text-[10px] uppercase text-[#6b6b6b]">
          <div>MODEL · PINN+XGB</div>
          <div className="mt-2">CITY · DELHI NCR</div>
        </div>
      </aside>

      <div className="ml-[240px] min-h-screen bg-black">
        <header className="h-12 border-b border-[#1a1a1a] px-6 flex items-center justify-between">
          <div className="font-mono text-[11px] uppercase text-[#6b6b6b]">{currentPage}</div>
          <div className="flex items-center gap-2 font-mono text-[10px] uppercase text-white">
            <span className="h-2 w-2 rounded-full bg-emerald-400" aria-hidden />
            PIPELINE READY
          </div>
        </header>

        <main className="min-h-[calc(100vh-3rem)] px-6 py-8 bg-black">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
