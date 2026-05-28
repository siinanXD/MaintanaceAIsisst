import { type ReactNode } from "react";

import { canWriteDashboard } from "../auth/permissions";
import { type DashboardPayload } from "./dashboardApi";
import { type DashboardViewState } from "./dashboardModel";
import {
  dashboardCriticalTasks,
  dashboardTaskGroupEmptyText,
  dashboardTaskGroups,
  taskDepartmentName,
  taskId,
  taskIsActive,
  taskPriorityBadgeClass,
  taskPriorityLabel,
  taskRelativeDateLabel,
  taskStatusBadgeClass,
  taskStatusLabel,
  taskText,
  taskUserLabel,
  type DashboardTaskGroupKey
} from "./dashboardTaskModel";

type DashboardTaskOverviewProps = {
  readonly dashboardState: DashboardViewState;
  readonly onOpenTask: (taskId: number) => void;
};

type CockpitColumn = {
  readonly id: string;
  readonly className: string;
  readonly title: ReactNode;
  readonly countKey: DashboardTaskGroupKey;
};

const COCKPIT_COLUMNS: readonly CockpitColumn[] = [
  {
    id: "cockpit-urgent-title",
    className: "is-urgent",
    title: "Dringend",
    countKey: "urgent"
  },
  {
    id: "cockpit-today-title",
    className: "is-today",
    title: <>Heute f&auml;llig</>,
    countKey: "today"
  },
  {
    id: "cockpit-progress-title",
    className: "is-progress",
    title: "In Arbeit",
    countKey: "progress"
  }
] as const;

/**
 * Render a compact task action button.
 */
function TaskActionButton({
  children,
  className,
  onClick
}: {
  readonly children: ReactNode;
  readonly className?: string;
  readonly onClick: () => void;
}): ReactNode {
  return (
    <button className={className ?? "btn btn-secondary btn-sm"} type="button" onClick={onClick}>
      {children}
    </button>
  );
}

/**
 * Render one status or priority badge for a cockpit task.
 */
function TaskBadge({ className, label }: { readonly className: string; readonly label: string }): ReactNode {
  return <span className={className}>{label}</span>;
}

/**
 * Render one React-owned cockpit task card.
 */
function CockpitTaskCard({
  task,
  onOpenTask
}: {
  readonly task: DashboardPayload;
  readonly onOpenTask: (taskId: number) => void;
}): ReactNode {
  const id = taskId(task);
  const canWriteTasks = canWriteDashboard("tasks");

  return (
    <article className="cockpit-task-card">
      <h4 className="cockpit-task-title">{taskText(task, "title", "Aufgabe")}</h4>
      <div className="flex flex-wrap gap-2">
        <TaskBadge className={taskPriorityBadgeClass(task.priority)} label={taskPriorityLabel(task.priority)} />
        <TaskBadge className={taskStatusBadgeClass(task.status)} label={taskStatusLabel(task.status)} />
      </div>
      <div className="cockpit-task-meta">
        {[taskDepartmentName(task), taskRelativeDateLabel(task), taskUserLabel(task.current_worker)]
          .filter((value) => value && value !== "-")
          .map((value) => (
            <span key={value}>{value}</span>
          ))}
      </div>
      <div className="cockpit-task-actions">
        <TaskActionButton onClick={() => onOpenTask(id)}>Details</TaskActionButton>
        {canWriteTasks && taskText(task, "status") === "open" ? (
          <TaskActionButton className="btn btn-primary btn-sm" onClick={() => onOpenTask(id)}>
            Starten
          </TaskActionButton>
        ) : null}
        {canWriteTasks && taskIsActive(task) ? (
          <TaskActionButton className="btn btn-success btn-sm text-white" onClick={() => onOpenTask(id)}>
            Erledigt
          </TaskActionButton>
        ) : null}
      </div>
    </article>
  );
}

/**
 * Render an empty cockpit column card.
 */
function EmptyCockpitCard({ groupKey }: { readonly groupKey: DashboardTaskGroupKey }): ReactNode {
  return (
    <article className="cockpit-task-card is-empty">
      <p>{dashboardTaskGroupEmptyText(groupKey)}</p>
      {canWriteDashboard("tasks") ? (
        <a className="btn btn-primary btn-sm" href="/tasks">
          Aufgaben öffnen
        </a>
      ) : null}
    </article>
  );
}

/**
 * Render one cockpit column for React-owned grouped tasks.
 */
function CockpitColumnPanel({
  column,
  onOpenTask,
  tasks
}: {
  readonly column: CockpitColumn;
  readonly onOpenTask: (taskId: number) => void;
  readonly tasks: readonly DashboardPayload[];
}): ReactNode {
  return (
    <section className={`cockpit-column ${column.className}`} aria-labelledby={column.id}>
      <h3 id={column.id} className="cockpit-column-title">
        {column.title} <span data-cockpit-count={column.countKey}>{tasks.length}</span>
      </h3>
      <div className="cockpit-task-list" data-cockpit-list={column.countKey}>
        {tasks.length ? (
          tasks.map((task) => <CockpitTaskCard key={taskId(task)} task={task} onOpenTask={onOpenTask} />)
        ) : (
          <EmptyCockpitCard groupKey={column.countKey} />
        )}
      </div>
    </section>
  );
}

/**
 * Render one critical task row for the top dashboard panel.
 */
function CriticalTaskItem({
  task,
  onOpenTask
}: {
  readonly task: DashboardPayload;
  readonly onOpenTask: (taskId: number) => void;
}): ReactNode {
  return (
    <article className="control-center-item is-critical">
      <span className="control-center-item-marker">TASK</span>
      <div>
        <strong>{taskText(task, "title", "Aufgabe")}</strong>
        <small>{[taskPriorityLabel(task.priority), taskDepartmentName(task), taskRelativeDateLabel(task)].filter(Boolean).join(" · ")}</small>
      </div>
      <button className="control-center-item-action" type="button" onClick={() => onOpenTask(taskId(task))}>
        Details
      </button>
    </article>
  );
}

/**
 * Render the critical-today dashboard panel with React-owned task data.
 */
function CriticalTodayPanel({ dashboardState, onOpenTask }: DashboardTaskOverviewProps): ReactNode {
  const criticalTasks = dashboardCriticalTasks(dashboardState.data);

  return (
    <article className="ops-panel app-card critical-today-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Heute zuerst</p>
          <h2>Kritisch heute</h2>
          <p className="panel-meta">
            Dringende Aufgaben, St&ouml;rungen und Engp&auml;sse mit direkter Aktion.
          </p>
        </div>
        <a data-dashboard-nav="tasks" hidden href="/tasks">
          Alle Aufgaben
        </a>
      </header>
      <div className="critical-today-list" data-dashboard-critical-today="">
        {dashboardState.isLoading ? <div className="empty-state">Kritische Lage wird geladen.</div> : null}
        {!dashboardState.isLoading && criticalTasks.length === 0 ? (
          <div className="empty-state">Keine kritischen Aufgaben.</div>
        ) : null}
        {criticalTasks.map((task) => (
          <CriticalTaskItem key={taskId(task)} task={task} onOpenTask={onOpenTask} />
        ))}
      </div>
    </article>
  );
}

/**
 * Render the dashboard task-priority panel with React-owned Kanban data.
 */
function TaskPriorityPanel({ dashboardState, onOpenTask }: DashboardTaskOverviewProps): ReactNode {
  const groups = dashboardTaskGroups(dashboardState.data.tasks);

  return (
    <article className="ops-panel app-card">
      <header className="ops-panel-header">
        <div>
          <p className="section-kicker">Priorit&auml;t</p>
          <h2>Offene Tasks</h2>
          <p className="panel-meta">
            Nach Dringlichkeit, F&auml;lligkeit und Status gruppiert.
          </p>
        </div>
        <a data-dashboard-nav="tasks" hidden href="/tasks">
          Kanban &ouml;ffnen
        </a>
      </header>
      <div className="priority-task-list" data-dashboard-priority-list="">
        {dashboardState.isLoading ? <div className="empty-state">Prioritäten werden geladen.</div> : null}
      </div>
      <div className="cockpit-board compact-cockpit-board" data-dashboard-task-board="">
        {COCKPIT_COLUMNS.map((column) => (
          <CockpitColumnPanel
            key={column.countKey}
            column={column}
            onOpenTask={onOpenTask}
            tasks={groups[column.countKey]}
          />
        ))}
      </div>
    </article>
  );
}

/**
 * Render the dashboard task overview panels as React-owned markup.
 */
export function DashboardTaskOverview(props: DashboardTaskOverviewProps): ReactNode {
  return (
    <>
      <CriticalTodayPanel {...props} />
      <TaskPriorityPanel {...props} />
    </>
  );
}
