import { type AdminAiPayload } from "./adminAiApi";

/**
 * Return payload list items from a collection response.
 */
export function payloadItems(payload: unknown): AdminAiPayload[] {
  const root = typeof payload === "object" && payload !== null ? payload as AdminAiPayload : {};
  const items = Array.isArray(root.items) ? root.items : Array.isArray(root.data) ? root.data : [];
  return items.filter((item): item is AdminAiPayload => typeof item === "object" && item !== null);
}
