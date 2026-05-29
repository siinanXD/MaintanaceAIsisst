import { type AdminAiPayload } from "./adminAiApi";
import { ragText } from "./adminAiRagBoardCore";
import type { AdminAiTrainingForm } from "./AdminAiRagBoardTypes";

/**
 * Normalize a training form into an API payload.
 */
export function trainingPayload(form: AdminAiTrainingForm): Record<string, unknown> {
  return {
    answer: form.answer.trim(),
    category: form.category.trim() || "wartung",
    department: form.department.trim(),
    is_active: form.isActive,
    keywords: form.keywords.trim(),
    priority: Number(form.priority || 50),
    question: form.question.trim(),
    title: form.title.trim()
  };
}

/**
 * Convert one API training entry into the editor form shape.
 */
export function trainingFormFromEntry(entry: AdminAiPayload): AdminAiTrainingForm {
  return {
    answer: ragText(entry.answer, ""),
    category: ragText(entry.category, ""),
    department: ragText(entry.department, ""),
    id: ragText(entry.id, ""),
    isActive: Boolean(entry.is_active),
    keywords: ragText(entry.keywords, ""),
    priority: ragText(entry.priority, "50"),
    question: ragText(entry.question, ""),
    title: ragText(entry.title, "")
  };
}
