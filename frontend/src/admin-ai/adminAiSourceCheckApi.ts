import { adminAiData, type AdminAiPayload } from "./adminAiApiCore";

/**
 * Run a prompt dry-run preview for the Source Check view.
 */
export async function testPromptDryRun(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/admin/ai/prompts/test", {
    body: payload,
    method: "POST"
  });
}

/**
 * Run a live AI chat call for the Source Check view.
 */
export async function runAiChat(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/ai/chat", {
    body: payload,
    method: "POST"
  });
}

/**
 * Store quality feedback for a Source Check result.
 */
export async function submitAiFeedback(payload: Record<string, unknown>): Promise<AdminAiPayload> {
  return adminAiData("/api/v1/ai/feedback", {
    body: payload,
    method: "POST"
  });
}
