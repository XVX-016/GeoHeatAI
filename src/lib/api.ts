/**
 * GeoHeatAI — typed fetch client for the FastAPI backend at localhost:8000.
 * All functions are plain async functions; wrap them in useQuery/useMutation
 * in the consuming components.
 */

const BASE_URL = "http://localhost:8000";

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ─── Response shapes ──────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  model: string;
  city: string;
  ml_model_status: string;
}

export interface Top3Driver {
  feature: string;
  mean_abs_shap_value: number;
}

export interface DriversResponse {
  feature_names: string[];
  mean_abs_shap: number[];
  top_3_drivers: Top3Driver[];
}

export interface ParetoSolution {
  solution_id: number;
  greening_pct: number;
  coolroof_pct: number;
  blueinfra_ha: number;
  delta_t_c: number;
  cost_cr: number;
  equity_score: number;
  zone_allocations?: number[][];
}

export interface RecommendedIntervention extends ParetoSolution {}

export interface SimulateParams {
  greening_pct: number;
  coolroof_pct: number;
  blueinfra_ha: number;
  zones: number[];
}

export interface SimulateResponse {
  delta_t_c: number;
  hotspots_eliminated: number;
  area_treated_km2: number;
  cost_cr: number;
}

// ─── API functions ─────────────────────────────────────────────────────────────

export const getHealth = (): Promise<HealthResponse> =>
  apiFetch<HealthResponse>("/api/health");

export const getDrivers = (): Promise<DriversResponse> =>
  apiFetch<DriversResponse>("/api/drivers");

export const getPareto = (): Promise<ParetoSolution[]> =>
  apiFetch<ParetoSolution[]>("/api/pareto");

export const getRecommended = (): Promise<RecommendedIntervention> =>
  apiFetch<RecommendedIntervention>("/api/scenarios/recommended");

export const simulateScenario = (params: SimulateParams): Promise<SimulateResponse> =>
  apiFetch<SimulateResponse>("/api/scenarios/simulate", {
    method: "POST",
    body: JSON.stringify(params),
  });
