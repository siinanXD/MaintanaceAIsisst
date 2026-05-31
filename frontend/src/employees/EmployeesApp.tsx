import { useEffect, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { canWriteDashboard } from "../auth/permissions";
import { ActionDrawer } from "../components/ui/ActionDrawer";
import { createActionDefinition } from "../components/ui/createActionSchema";
import { loadEmployees } from "./employeeApi";
import { EmployeeEditDialog } from "./components/EmployeeEditDialog";
import { EmployeeFormPanel } from "./components/EmployeeFormPanel";
import { EmployeeHeader } from "./components/EmployeeHeader";
import { EmployeeList } from "./components/EmployeeList";
import { EmployeeStats } from "./components/EmployeeStats";
import type { Employee, EmployeeDraft, MessageState } from "./employeeTypes";
import { canManageEmployees, EMPTY_EMPLOYEE_DRAFT, employeeErrorMessage } from "./employeeUtils";

const EMPLOYEES_ISLAND = {
  mountedFlag: "maintenanceEmployeesReactMounted",
  mountEvent: "maintenance-employees-react-mounted"
};

/**
 * Render the React employees workflow island.
 */
export function EmployeesApp(): ReactNode {
  const writable = canWriteDashboard("employees");
  const manageable = canManageEmployees(writable);
  const [isCreateDrawerOpen, setIsCreateDrawerOpen] = useState(false);
  const [createDraft, setCreateDraft] = useState<EmployeeDraft>({ ...EMPTY_EMPLOYEE_DRAFT });
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null);
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [message, setMessage] = useState<MessageState>({ text: "", error: false });

  /**
   * Refresh all visible employee rows.
   */
  async function refreshEmployees(): Promise<void> {
    setEmployees(await loadEmployees());
  }

  useEffect(() => {
    markIslandMounted(EMPLOYEES_ISLAND);
  }, []);

  useEffect(() => {
    refreshEmployees().catch((error: unknown) => {
      setMessage({ text: employeeErrorMessage(error), error: true });
    });
    if (window.location.hash === "#employee-create") {
      setIsCreateDrawerOpen(true);
    }
  }, []);

  return (
    <>
      <EmployeeHeader manageable={manageable} onCreateEmployee={() => setIsCreateDrawerOpen(true)} />
      <EmployeeStats employees={employees} />
      <section className="dashboard-grid">
        {!manageable && message.text ? (
          <section className="card app-card lg:col-span-12" role="status">
            <div className="card-body">
              <p className={`panel-meta${message.error ? " is-error" : ""}`} data-employee-message>{message.text}</p>
            </div>
          </section>
        ) : null}
        <EmployeeList
          employees={employees}
          manageable={manageable}
          onEdit={setEditingEmployee}
          onMessageChange={setMessage}
          onMutated={refreshEmployees}
        />
      </section>
      <EmployeeEditDialog
        employee={editingEmployee}
        onClose={() => setEditingEmployee(null)}
        onMessageChange={setMessage}
        onSaved={refreshEmployees}
      />
      <ActionDrawer
        definition={createActionDefinition("employeeCreate")}
        isOpen={isCreateDrawerOpen}
        onClose={() => setIsCreateDrawerOpen(false)}
      >
        <EmployeeFormPanel
          drawerMode
          draft={createDraft}
          hidden={!manageable}
          message={message}
          onDraftChange={setCreateDraft}
          onMessageChange={setMessage}
          onSaved={async () => {
            await refreshEmployees();
            setIsCreateDrawerOpen(false);
          }}
        />
      </ActionDrawer>
    </>
  );
}
