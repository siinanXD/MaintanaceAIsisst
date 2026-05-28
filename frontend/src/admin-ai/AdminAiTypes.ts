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

export const ADMIN_AI_NAVIGATION: readonly AdminAiNavigationItem[] = [
  {
    description: "Ampeln, Top-Fragen, Wissenslücken, Kostenstatus und letzte Fehler.",
    href: "/admin/ai",
    label: "Cockpit",
    number: "00",
    view: "overview",
  },
  {
    description: "Quellen-Kacheln, Index-Fortschritt und offene Pflegeaktionen.",
    href: "/admin/ai/rag-board",
    label: "RAG-Spielbrett",
    number: "01",
    view: "rag_board",
  },
  {
    description: "Testfragen, Antwortqualität, Quellenbewertung und FAQ-Folgeaktionen.",
    href: "/admin/ai/source-check",
    label: "Quellenprüfung",
    number: "02",
    view: "source_check",
  },
  {
    description: "Prompt-Versionen, häufige Fragen, Antwortbausteine und Freigaben.",
    href: "/admin/ai/prompt-faq",
    label: "Prompt & FAQ",
    number: "03",
    view: "prompt_faq",
  },
  {
    description: "Nutzerkosten, Workflowkosten, Feedbackrate und No-Source-Rate.",
    href: "/admin/ai/effectiveness",
    label: "Kosten & Effektivität",
    number: "04",
    view: "effectiveness",
  },
  {
    description: "Retrieval, Reindex, Observability, Debug und SLO-Diagnose.",
    href: "/admin/ai/technical",
    label: "Technik",
    number: "05",
    view: "technical",
  },
];

const PATH_TO_VIEW: Readonly<Record<string, AdminAiView>> = {
  "/admin/ai": "overview",
  "/admin/ai/": "overview",
  "/admin/ai/rag-board": "rag_board",
  "/admin/ai/source-check": "source_check",
  "/admin/ai/prompt-faq": "prompt_faq",
  "/admin/ai/effectiveness": "effectiveness",
  "/admin/ai/technical": "technical",
};

/**
 * Resolve the canonical Admin-AI view from the current browser path.
 */
export function resolveAdminAiViewFromPathname(pathname: string): AdminAiView {
  return PATH_TO_VIEW[pathname] ?? "overview";
}
