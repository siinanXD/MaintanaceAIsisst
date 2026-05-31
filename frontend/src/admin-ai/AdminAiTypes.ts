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
    description: "AI-Status, Quellen, Kostenstatus, Top-Probleme und offene Admin-Aktionen.",
    href: "/admin/ai",
    label: "Overview",
    number: "01",
    view: "overview"
  },
  {
    description: "Dokumente, FAQ, Trainingswissen, Fehlerkatalog, Aufgaben und Maschinen.",
    href: "/admin/ai/rag-board",
    label: "Knowledge & Sources",
    number: "02",
    view: "rag_board"
  },
  {
    description: "Testfragen, Workflows, Dry-run/Live, Quellen, Sicherheit, Latenz und Kosten.",
    href: "/admin/ai/source-check",
    label: "Test & Quality",
    number: "03",
    view: "source_check"
  },
  {
    description: "Prompt-Versionen, Entwuerfe, Rollback, FAQ-Entwuerfe und Wissensluecken.",
    href: "/admin/ai/prompt-faq",
    label: "Prompts & FAQ",
    number: "04",
    view: "prompt_faq"
  },
  {
    description: "Tokens, geschaetzte Kosten, Nutzerkosten, Workflowkosten und Fallback-Rate.",
    href: "/admin/ai/effectiveness",
    label: "Costs & Usage",
    number: "05",
    view: "effectiveness"
  },
  {
    description: "Recall@K, MRR, NDCG, Similarity, Chunk-Details, Latenz und Vektor-Sync.",
    href: "/admin/ai/technical",
    label: "Technology & Operations",
    number: "06",
    view: "technical"
  }
];

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
