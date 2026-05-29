import { type AdminAiPayload } from "./adminAiApi";
import { type AdminAiSourceCheckState } from "./adminAiSourceCheckModel";

export type AdminAiRagBoardFilters = {
  readonly knowledgeQuality: string;
  readonly knowledgeQuery: string;
  readonly knowledgeSource: string;
  readonly knowledgeStatus: string;
  readonly networkFocus: string;
  readonly networkFocusType: string;
  readonly networkQuality: string;
  readonly networkQuery: string;
  readonly networkSource: string;
  readonly trainingActive: string;
  readonly trainingQuery: string;
};

export type AdminAiTrainingForm = {
  readonly answer: string;
  readonly category: string;
  readonly department: string;
  readonly id: string;
  readonly isActive: boolean;
  readonly keywords: string;
  readonly priority: string;
  readonly question: string;
  readonly title: string;
};

export type AdminAiRagBoardState = {
  readonly errorMessage: string;
  readonly filters: AdminAiRagBoardFilters;
  readonly isLoading: boolean;
  readonly isSaving: boolean;
  readonly jobs: readonly AdminAiPayload[];
  readonly knowledge: readonly AdminAiPayload[];
  readonly knowledgeStatus: AdminAiPayload | null;
  readonly network: AdminAiPayload | null;
  readonly statusMessage: string;
  readonly training: readonly AdminAiPayload[];
  readonly trainingForm: AdminAiTrainingForm;
};

export const EMPTY_RAG_BOARD_FILTERS: AdminAiRagBoardFilters = {
  knowledgeQuality: "",
  knowledgeQuery: "",
  knowledgeSource: "",
  knowledgeStatus: "",
  networkFocus: "",
  networkFocusType: "",
  networkQuality: "",
  networkQuery: "",
  networkSource: "",
  trainingActive: "",
  trainingQuery: ""
};

export const EMPTY_TRAINING_FORM: AdminAiTrainingForm = {
  answer: "",
  category: "",
  department: "",
  id: "",
  isActive: true,
  keywords: "",
  priority: "50",
  question: "",
  title: ""
};

export const EMPTY_ADMIN_AI_RAG_BOARD_STATE: AdminAiRagBoardState = {
  errorMessage: "",
  filters: EMPTY_RAG_BOARD_FILTERS,
  isLoading: false,
  isSaving: false,
  jobs: [],
  knowledge: [],
  knowledgeStatus: null,
  network: null,
  statusMessage: "",
  training: [],
  trainingForm: EMPTY_TRAINING_FORM
};

export const QUALITY_STATUSES = [
  "draft",
  "ai_suggested",
  "technician_confirmed",
  "admin_approved",
  "low_quality",
  "duplicate",
  "outdated",
  "rejected"
] as const;

export const RAG_SOURCE_DEFINITIONS = [
  {
    description: "Uploads, Berichte und Maschinenhandbücher",
    icon: "D",
    key: "documents",
    label: "Dokumente",
    types: ["upload", "generated_document", "machine_manual", "maintenance_plan"]
  },
  {
    description: "Freigegebene Fragen und Antworten",
    icon: "F",
    key: "faq",
    label: "FAQ",
    types: ["faq"]
  },
  {
    description: "Manuelles Assistant-Training",
    icon: "T",
    key: "training",
    label: "Trainingswissen",
    types: ["manual_training"]
  },
  {
    description: "Fehlercodes, Ursachen und Lösungen",
    icon: "!",
    key: "error_catalog",
    label: "Fehlerkatalog",
    types: ["error_entry"]
  },
  {
    description: "Wartungs- und Eskalationsaufgaben",
    icon: "A",
    key: "tasks",
    label: "Aufgaben",
    types: ["task"]
  },
  {
    description: "Anlagen, Komponenten und Maschinenkontext",
    icon: "M",
    key: "machines",
    label: "Maschinen",
    types: ["machine"]
  }
] as const;

export type AdminAiRagBoardProps = {
  readonly onCreateFaq: () => void;
  readonly onDeleteKnowledge: (documentId: number) => void;
  readonly onDeleteTraining: (entryId: number) => void;
  readonly onFeedback: (rating: string, comment?: string) => void;
  readonly onKnowledgeFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onKnowledgeUpload: (form: HTMLFormElement) => void;
  readonly onNetworkFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onQueueDocument: (documentId: number) => void;
  readonly onQueueStale: () => void;
  readonly onReindexAll: () => void;
  readonly onReindexDocument: (documentId: number) => void;
  readonly onReindexStale: () => void;
  readonly onReset: () => void;
  readonly onSaveTraining: (form: AdminAiTrainingForm) => void;
  readonly onSelectTraining: (entry: Record<string, unknown>) => void;
  readonly onSourceTestSubmit: (form: HTMLFormElement, intent?: string) => void;
  readonly onTrainingFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onTrainingFormChange: (form: AdminAiTrainingForm) => void;
  readonly onUpdateKnowledgeQuality: (documentId: number, qualityStatus: string) => void;
  readonly ragBoardState: AdminAiRagBoardState;
  readonly sourceCheckState: AdminAiSourceCheckState;
};
