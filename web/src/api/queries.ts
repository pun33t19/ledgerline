import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Controls, Coverage, RunSummary, ScenarioInfo } from "./types";

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: () => api<ScenarioInfo[]>("/api/scenarios"),
    staleTime: Infinity,
  });
}

export function useCoverage() {
  return useQuery({
    queryKey: ["coverage"],
    queryFn: () => api<Coverage>("/api/coverage"),
    staleTime: Infinity,
  });
}

export function useStartRun() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { scenario_id: string; controls: Controls }) =>
      api<RunSummary>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["runs"] }),
  });
}
