import { apiRequest } from "../api/client";
import { listData, unwrapData } from "../api/payload";
import type {
  Machine,
  MachineAssistantResponse,
  MachineDraft,
  MachineHistory,
  MachineProfile,
  MachineRecommendation
} from "./machineTypes";

/**
 * Load all machines visible to the current user.
 */
export async function loadMachines(): Promise<Machine[]> {
  const response = await apiRequest<unknown>("/api/v1/machines?limit=200");
  return listData<Machine>(response);
}

/**
 * Create a machine through the existing API.
 */
export async function createMachine(draft: MachineDraft): Promise<Machine> {
  return apiRequest<Machine>("/api/v1/machines", {
    method: "POST",
    body: {
      name: draft.name,
      produced_item: draft.produced_item,
      required_employees: Number(draft.required_employees || 1)
    }
  });
}

/**
 * Update a machine through the existing API.
 */
export async function updateMachine(machineId: number, draft: MachineDraft): Promise<Machine> {
  return apiRequest<Machine>(`/api/v1/machines/${machineId}`, {
    method: "PUT",
    body: {
      name: draft.name,
      produced_item: draft.produced_item,
      required_employees: Number(draft.required_employees || 1)
    }
  });
}

/**
 * Delete one machine through the existing API.
 */
export async function deleteMachine(machineId: number): Promise<void> {
  await apiRequest<null>(`/api/v1/machines/${machineId}`, { method: "DELETE" });
}

/**
 * Load one machine history through the existing API.
 */
export async function loadMachineHistory(machineId: number): Promise<MachineHistory> {
  return unwrapData<MachineHistory>(await apiRequest<unknown>(`/api/v1/machines/${machineId}/history`));
}

/**
 * Ask the existing machine assistant endpoint.
 */
export async function askMachineAssistant(
  machineId: number,
  question: string
): Promise<MachineAssistantResponse> {
  return unwrapData<MachineAssistantResponse>(
    await apiRequest<unknown>(`/api/v1/machines/${machineId}/assistant`, {
      method: "POST",
      body: { question }
    })
  );
}

/**
 * Load preventive maintenance recommendations.
 */
export async function loadMaintenanceRecommendations(): Promise<MachineRecommendation[]> {
  const response = await apiRequest<unknown>("/api/v1/machines/maintenance-recommendations?limit=5");
  const payload = unwrapData<unknown>(response);

  if (Array.isArray(payload)) {
    return payload as MachineRecommendation[];
  }

  if (typeof payload === "object" && payload !== null && "items" in payload) {
    const items = (payload as { readonly items?: unknown }).items;
    return Array.isArray(items) ? items as MachineRecommendation[] : [];
  }

  return [];
}

/**
 * Load the full machine profile.
 */
export async function loadMachineProfile(machineId: number): Promise<MachineProfile> {
  return unwrapData<MachineProfile>(await apiRequest<unknown>(`/api/v1/machines/${machineId}/profile`));
}
