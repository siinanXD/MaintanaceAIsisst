import { type AdminAiPayload } from "./adminAiApi";
import { type AdminAiSourceCheckProps } from "./AdminAiSectionsSourceCheck";
import {
  type AdminAiRagBoardFilters,
  type AdminAiRagBoardState,
  type AdminAiTrainingForm
} from "./adminAiRagBoardModel";

export type AdminAiRagBoardProps = AdminAiSourceCheckProps & {
  readonly onDeleteKnowledge: (documentId: number) => void;
  readonly onDeleteTraining: (entryId: number) => void;
  readonly onKnowledgeFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onKnowledgeUpload: (form: HTMLFormElement) => void;
  readonly onNetworkFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onQueueDocument: (documentId: number) => void;
  readonly onQueueStale: () => void;
  readonly onReindexAll: () => void;
  readonly onReindexDocument: (documentId: number) => void;
  readonly onReindexStale: () => void;
  readonly onSaveTraining: (form: AdminAiTrainingForm) => void;
  readonly onSelectTraining: (entry: AdminAiPayload) => void;
  readonly onTrainingFilterChange: (key: keyof AdminAiRagBoardFilters, value: string) => void;
  readonly onTrainingFormChange: (form: AdminAiTrainingForm) => void;
  readonly onUpdateKnowledgeQuality: (documentId: number, qualityStatus: string) => void;
  readonly ragBoardState: AdminAiRagBoardState;
};
