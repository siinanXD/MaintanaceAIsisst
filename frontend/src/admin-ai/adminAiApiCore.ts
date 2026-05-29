import { apiRequest } from "../api/client";
import { unwrapData } from "../api/payload";

export type AdminAiPayload = Record<string, unknown>;

/**
 * Request one Admin-AI payload and unwrap the standard API data envelope.
 */
export async function adminAiData(
  path: string,
  options: Parameters<typeof apiRequest>[1] = {}
): Promise<AdminAiPayload> {
  return unwrapData<AdminAiPayload>(await apiRequest(path, options));
}
