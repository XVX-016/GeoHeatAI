/**
 * GeoHeatAI — typed fetch client for the FastAPI backend at localhost:8000.
 */

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers as Record<string, string> | undefined) },
  });

  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} failed (${res.status}): ${msg}`);
  }

  return res.json() as Promise<T>;
}

export interface HealthResponse {
  status: string;
  model: string;
  city: string;
  isMock?: boolean;
}

export interface DriversResponse {
  features: string[];
  shap_values: number[];
  top_3: string[];
  isMock?: boolean;
}

export interface ParetoSolution {
  solution_id: string;
  greening_pct: number;
  coolroof_pct: number;
  blueinfra_ha: number;
  delta_t_c: number;
  cost_cr: number;
  equity_score: number;
}

export interface SimulateRequest {
  greening_pct: number;
  coolroof_pct: number;
  blueinfra_ha: number;
  zones: string[];
}

export interface SimulateResponse {
  delta_t_c: number;
  hotspots_eliminated: number;
  area_treated_km2: number;
  cost_cr: number;
}

function normalizeDrivers(payload: any): DriversResponse {
  const featureNames = Array.isArray(payload?.feature_names) ? payload.feature_names : [];
  const shapValues = Array.isArray(payload?.mean_abs_shap) ? payload.mean_abs_shap : [];
  const top3 = Array.isArray(payload?.top_3_drivers)
    ? payload.top_3_drivers.map((item: any) => item?.feature ?? "")
    : [];

  return {
    features: featureNames,
    shap_values: shapValues,
    top_3: top3,
  };
}

function normalizePareto(payload: any[]): ParetoSolution[] {
  return (payload ?? []).map((solution: any) => ({
    solution_id: String(solution?.solution_id ?? ""),
    greening_pct: Number(solution?.greening_pct ?? 0),
    coolroof_pct: Number(solution?.coolroof_pct ?? 0),
    blueinfra_ha: Number(solution?.blueinfra_ha ?? 0),
    delta_t_c: Number(solution?.delta_t_c ?? 0),
    cost_cr: Number(solution?.cost_cr ?? 0),
    equity_score: Number(solution?.equity_score ?? 0),
  }));
}

function normalizeRecommended(payload: any): ParetoSolution {
  return {
    solution_id: String(payload?.solution_id ?? ""),
    greening_pct: Number(payload?.greening_pct ?? 0),
    coolroof_pct: Number(payload?.coolroof_pct ?? 0),
    blueinfra_ha: Number(payload?.blueinfra_ha ?? 0),
    delta_t_c: Number(payload?.delta_t_c ?? 0),
    cost_cr: Number(payload?.cost_cr ?? 0),
    equity_score: Number(payload?.equity_score ?? 0),
  };
}

function normalizeSimulate(payload: any): SimulateResponse {
  return {
    delta_t_c: Number(payload?.delta_t_c ?? 0),
    hotspots_eliminated: Number(payload?.hotspots_eliminated ?? 0),
    area_treated_km2: Number(payload?.area_treated_km2 ?? 0),
    cost_cr: Number(payload?.cost_cr ?? 0),
  };
}

function normalizeZones(zones: string[]): number[] {
  if (zones.includes("all")) return Array.from({ length: 50 }, (_, index) => index);
  return zones.map((zone) => Number(zone));
}

// Stably generated mock Pareto solutions
const MOCK_PARETO: ParetoSolution[] = Array.from({ length: 40 }, (_, i) => {
  const idStr = String(i + 1).padStart(2, "0");
  return {
    solution_id: `P-${idStr}`,
    greening_pct: Math.floor(8 + Math.random() * 25), // 8 to 32
    coolroof_pct: Math.floor(30 + Math.random() * 51), // 30 to 80
    blueinfra_ha: Math.floor(20 + Math.random() * 281), // 20 to 300
    delta_t_c: -(0.6 + Math.random() * 2.8), // -0.6 to -3.4
    cost_cr: Math.floor(800 + Math.random() * 5401), // 800 to 6200
    equity_score: parseFloat((0.45 + Math.random() * 0.47).toFixed(4)), // 0.45 to 0.92
  };
});

export const api = {
  health: async () => {
    try {
      const payload = await apiFetch<any>("/api/health");
      return {
        status: payload.status ?? "ok",
        model: payload.model ?? "Unknown",
        city: payload.city ?? "Delhi NCR",
        isMock: false,
      } satisfies HealthResponse;
    } catch (err) {
      return {
        status: "ok",
        model: "XGBoost+PINN",
        city: "Delhi NCR",
        isMock: true,
      } satisfies HealthResponse;
    }
  },
  drivers: async () => {
    try {
      const payload = await apiFetch<any>("/api/drivers");
      return {
        ...normalizeDrivers(payload),
        isMock: false,
      };
    } catch (err) {
      return {
        features: ["NDVI", "Building Density", "Albedo", "Air Temp", 
                   "SVF", "Impervious Surface", "Wind Speed", "Humidity"],
        shap_values: [-0.34, 0.28, -0.22, 0.19, 0.16, 0.14, -0.09, -0.07],
        top_3: [
          "NDVI deficit is the dominant cooling signal — each 0.1 unit increase suppresses LST by ~1.4°C in low-albedo zones.",
          "Building density drives 28% of daytime heating via impervious surface radiation trapping.",
          "Sky View Factor controls nocturnal heat retention — high SVF zones show 2.1°C lower night-minimum LST."
        ],
        isMock: true,
      };
    }
  },
  pareto: async () => {
    try {
      const payload = await apiFetch<any[]>("/api/pareto");
      return normalizePareto(payload);
    } catch (err) {
      return MOCK_PARETO;
    }
  },
  recommended: async () => {
    try {
      const payload = await apiFetch<any>("/api/scenarios/recommended");
      return normalizeRecommended(payload);
    } catch (err) {
      return MOCK_PARETO[0];
    }
  },
  simulate: async (params: SimulateRequest) => {
    try {
      const payload = await apiFetch<any>("/api/scenarios/simulate", {
        method: "POST",
        body: JSON.stringify({
          greening_pct: params.greening_pct,
          coolroof_pct: params.coolroof_pct,
          blueinfra_ha: params.blueinfra_ha,
          zones: normalizeZones(params.zones),
        }),
      });
      return normalizeSimulate(payload);
    } catch (err) {
      return {
        delta_t_c: -(params.greening_pct * 0.08 + params.coolroof_pct * 0.018 + params.blueinfra_ha * 0.004),
        hotspots_eliminated: Math.round(params.greening_pct * 0.6),
        area_treated_km2: params.greening_pct * 4.2 + params.coolroof_pct * 1.8,
        cost_cr: params.greening_pct * 120 + params.coolroof_pct * 80 + params.blueinfra_ha * 40,
      };
    }
  },
} as const;

export const getHealth = api.health;
export const getDrivers = api.drivers;
export const getPareto = api.pareto;
export const getRecommended = api.recommended;
export const simulateScenario = api.simulate;
