export type AdminAiView =
  | "overview"
  | "rag_board"
  | "source_check"
  | "prompt_faq"
  | "effectiveness"
  | "technical";

export type AdminAiNavigationItem = {
  readonly description: string;
  readonly href: string;
  readonly label: string;
  readonly number: string;
  readonly view: AdminAiView;
};

export { ADMIN_AI_NAVIGATION, ADMIN_AI_PRIMARY_NAVIGATION } from "./adminAiViewMeta";

const PATH_TO_VIEW: Readonly<Record<string, AdminAiView>> = {
  "/admin/ai": "overview",
  "/admin/ai/": "overview",
  "/admin/ai/rag-board": "rag_board",
  "/admin/ai/source-check": "source_check",
  "/admin/ai/prompt-faq": "prompt_faq",
  "/admin/ai/effectiveness": "effectiveness",
  "/admin/ai/technical": "technical"
};

/**
 * Resolve the canonical Admin-AI view from the current browser path.
 */
export function resolveAdminAiViewFromPathname(pathname: string): AdminAiView {
  return PATH_TO_VIEW[pathname] ?? "overview";
}
