import {
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";

import { markIslandMounted } from "../app/islandMount";
import { canWriteDashboard } from "../auth/permissions";
import { loadDepartments, loadTasks, prioritizeTasks } from "./taskApi";
import { TaskBoard } from "./components/TaskBoard";
import { TaskFormPanel } from "./components/TaskFormPanel";
import { TaskHeader } from "./components/TaskHeader";
import { TaskPriorityPanel } from "./components/TaskPriorityPanel";
import { TaskStats } from "./components/TaskStats";
import { TaskSuggestionPanel } from "./components/TaskSuggestionPanel";
import type {
  Department,
  MessageState,
  Task,
  TaskDraft,
  TaskFilters,
  TaskPriorityItem
} from "./taskTypes";
import {
  consumeTaskActionPreview,
  createEmptyTaskDraft,
  draftFromTask,
  initialTaskSearchQuery,
  taskErrorMessage,
  taskMatchesFilters,
  taskSortScore
} from "./taskUtils";

const TASKS_ISLAND = {
  mountedFlag: "maintenanceTasksReactMounted",
  mountEvent: "maintenance-tasks-react-mounted"
};

/**
 * Return the visible department filter options from loaded tasks.
 */
function departmentOptionsFromTasks(tasks: readonly Task[]): string[] {
  return Array.from(new Set(
    tasks.map((task) => task.department?.name).filter((name): name is string => Boolean(name))
  )).sort((first, second) => first.localeCompare(second, "de-DE"));
}

/**
 * Render the React task workflow island.
 */
export function TasksApp(): ReactNode {
  const writable = canWriteDashboard("tasks");
  const [departments, setDepartments] = useState<Department[]>([]);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [filters, setFilters] = useState<TaskFilters>({
    search: initialTaskSearchQuery(),
    status: "",
    priority: "",
    department: "",
    due: ""
  });
  const [formDraft, setFormDraft] = useState<TaskDraft>(createEmptyTaskDraft());
  const [message, setMessage] = useState<MessageState>({ text: "", error: false });
  const [priorityBusy, setPriorityBusy] = useState(false);
  const [priorityHint, setPriorityHint] = useState({
    title: "Bei Bedarf aktualisieren",
    text: "Die Task-Seite lädt ohne automatische AI-Priorisierung. Nutze Aktualisieren, wenn du eine neue Risikoreihenfolge brauchst."
  });
  const [priorityItems, setPriorityItems] = useState<TaskPriorityItem[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);

  const departmentOptions = useMemo(() => departmentOptionsFromTasks(tasks), [tasks]);
  const visibleTasks = useMemo(() => (
    tasks
      .filter((task) => taskMatchesFilters(task, filters))
      .sort((first, second) => taskSortScore(first).localeCompare(taskSortScore(second)))
  ), [filters, tasks]);

  /**
   * Load departments and visible tasks in parallel.
   */
  async function refreshTaskData(): Promise<void> {
    const [loadedDepartments, loadedTasks] = await Promise.all([
      loadDepartments(),
      loadTasks()
    ]);
    setDepartments(loadedDepartments);
    setTasks(loadedTasks);
  }

  /**
   * Mark the manual priority result stale after task mutations.
   */
  function markPrioritiesStale(): void {
    setPriorityItems([]);
    setPriorityHint({
      title: "Prioritätslage nicht neu berechnet",
      text: "Die Aufgaben wurden geändert. Aktualisiere die Prioritätslage bei Bedarf manuell."
    });
  }

  /**
   * Load manual task priorities on explicit user action.
   */
  async function refreshPriorities(): Promise<void> {
    setPriorityBusy(true);
    setPriorityHint({
      title: "Priorisierung läuft",
      text: "Die wichtigsten offenen Aufgaben werden neu bewertet."
    });

    try {
      const priorities = await prioritizeTasks();
      setPriorityItems(priorities);
      if (!priorities.length) {
        setPriorityHint({
          title: "Keine offenen Aufgaben",
          text: "Wenn Arbeit entsteht, lege eine Aufgabe an oder nutze den AI-Vorschlag aus einer kurzen Beschreibung."
        });
      }
    } catch {
      setPriorityItems([]);
      setPriorityHint({
        title: "Priorisierung konnte nicht geladen werden.",
        text: "Die Aufgabenliste bleibt nutzbar. Prüfe später erneut oder sortiere nach Fälligkeit und Risiko."
      });
    } finally {
      setPriorityBusy(false);
    }
  }

  /**
   * Cancel the current task edit state.
   */
  function cancelEdit(): void {
    setEditingTaskId(null);
    setFormDraft(createEmptyTaskDraft());
    setMessage({ text: "Bearbeitung abgebrochen.", error: false });
  }

  /**
   * Open the task form in edit mode.
   */
  function editTask(task: Task): void {
    setEditingTaskId(task.id);
    setFormDraft(draftFromTask(task));
    window.requestAnimationFrame(() => {
      document.querySelector("[data-task-form]")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  /**
   * Apply draft data from AI preview or suggestion to the form.
   */
  function applyDraft(draft: TaskDraft): void {
    setEditingTaskId(null);
    setFormDraft(draft);
    window.requestAnimationFrame(() => {
      document.querySelector("[data-task-form]")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  /**
   * Refresh data after create or update operations.
   */
  async function handleTaskSaved(): Promise<void> {
    setEditingTaskId(null);
    await refreshTaskData();
    markPrioritiesStale();
  }

  useEffect(() => {
    markIslandMounted(TASKS_ISLAND);
  }, []);

  useEffect(() => {
    refreshTaskData().catch((error: unknown) => {
      setMessage({ text: taskErrorMessage(error), error: true });
    });

    const previewDraft = consumeTaskActionPreview();
    if (previewDraft) {
      setFormDraft(previewDraft);
    }
  }, []);

  return (
    <>
      <TaskHeader onRefreshPriorities={refreshPriorities} priorityBusy={priorityBusy} writable={writable} />
      <TaskStats tasks={tasks} />
      <section className="task-workflow-grid" aria-label="Aufgaben Workflows">
        <TaskFormPanel
          departments={departments}
          draft={formDraft}
          editingTaskId={editingTaskId}
          hidden={!writable}
          message={message}
          onCancelEdit={cancelEdit}
          onDraftChange={setFormDraft}
          onMessageChange={setMessage}
          onSaved={handleTaskSaved}
        />
        <TaskSuggestionPanel hidden={!writable} onApplySuggestion={applyDraft} />
        <TaskPriorityPanel
          busy={priorityBusy}
          hint={priorityHint}
          items={priorityItems}
          onRefresh={refreshPriorities}
        />
      </section>
      <TaskBoard
        allTasks={tasks}
        departmentOptions={departmentOptions}
        filters={filters}
        onEdit={editTask}
        onFiltersChange={setFilters}
        onMessageChange={setMessage}
        onMutated={refreshTaskData}
        onPrioritiesStale={markPrioritiesStale}
        tasks={visibleTasks}
        writable={writable}
      />
    </>
  );
}
