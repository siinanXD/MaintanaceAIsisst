import { type ReactNode } from "react";

import { ShiftplansEditDialog } from "./ShiftplansEditDialog";
import { ShiftplansGenerationForm } from "./ShiftplansGenerationForm";
import { ShiftplansHero } from "./ShiftplansHero";
import { ShiftplansPlanView } from "./ShiftplansPlanView";
import type {
  Machine,
  ShiftModel,
  ShiftPlan,
  ShiftplanChangeLog,
  ShiftplanEditDraft,
  ShiftplanEntry,
  ShiftplansMessage,
  ShiftplanDraft,
  ShiftplanWarning,
} from "./ShiftplansTypes";

type ShiftplansMarkupProps = {
  readonly busyAction: "generate" | "preview" | null;
  readonly changelog: readonly ShiftplanChangeLog[];
  readonly currentPlan: ShiftPlan | null;
  readonly deletingEntry: boolean;
  readonly dialogEntry: ShiftplanEntry | null;
  readonly dialogMessage: ShiftplansMessage;
  readonly draft: ShiftplanDraft;
  readonly formMessage: ShiftplansMessage;
  readonly isAdmin: boolean;
  readonly machines: readonly Machine[];
  readonly models: readonly ShiftModel[];
  readonly onDeleteEntry: (entry: ShiftplanEntry) => void;
  readonly onDeletePlan: () => void;
  readonly onDialogClose: () => void;
  readonly onDialogSave: (entry: ShiftplanEntry, draft: ShiftplanEditDraft) => void;
  readonly onDownload: () => void;
  readonly onDraftChange: (draft: ShiftplanDraft) => void;
  readonly onEditEntry: (entry: ShiftplanEntry) => void;
  readonly onGenerate: () => void;
  readonly onMachineToggle: (machineId: number, checked: boolean) => void;
  readonly onMoveEntryToEntry: (entryId: number, targetEntryId: number) => void;
  readonly onMoveEntryToSlot: (entryId: number, targetDate: string, targetShift: string) => void;
  readonly onPlanSelect: (index: number) => void;
  readonly onPreview: () => void;
  readonly onPrint: () => void;
  readonly onPublish: () => void;
  readonly plans: readonly ShiftPlan[];
  readonly savingEntry: boolean;
  readonly selectedMachineIds: ReadonlySet<number>;
  readonly selectedPlanIndex: number;
  readonly warnings: readonly ShiftplanWarning[];
  readonly writable: boolean;
};

/**
 * Render the full shift planning page with React-owned behavior.
 */
export function ShiftplansMarkup(props: ShiftplansMarkupProps): ReactNode {
  return (
    <>
      <ShiftplansHero />
      <section className="dashboard-grid">
        <ShiftplansGenerationForm
          busyAction={props.busyAction}
          draft={props.draft}
          machines={props.machines}
          message={props.formMessage}
          models={props.models}
          onDraftChange={props.onDraftChange}
          onGenerate={props.onGenerate}
          onMachineToggle={props.onMachineToggle}
          onPreview={props.onPreview}
          selectedMachineIds={props.selectedMachineIds}
          writable={props.writable}
        />
        <ShiftplansPlanView
          changelog={props.changelog}
          currentPlan={props.currentPlan}
          isAdmin={props.isAdmin}
          onDeleteEntry={props.onDeleteEntry}
          onDeletePlan={props.onDeletePlan}
          onDownload={props.onDownload}
          onEditEntry={props.onEditEntry}
          onMoveEntryToEntry={props.onMoveEntryToEntry}
          onMoveEntryToSlot={props.onMoveEntryToSlot}
          onPlanSelect={props.onPlanSelect}
          onPrint={props.onPrint}
          onPublish={props.onPublish}
          plans={props.plans}
          selectedPlanIndex={props.selectedPlanIndex}
          warnings={props.warnings}
          writable={props.writable}
        />
      </section>
      <ShiftplansEditDialog
        deleting={props.deletingEntry}
        entry={props.dialogEntry}
        isAdmin={props.isAdmin}
        message={props.dialogMessage}
        onClose={props.onDialogClose}
        onDelete={props.onDeleteEntry}
        onSave={props.onDialogSave}
        saving={props.savingEntry}
      />
    </>
  );
}
