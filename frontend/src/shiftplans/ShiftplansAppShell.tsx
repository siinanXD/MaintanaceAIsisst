import { type Dispatch, type ReactNode, type SetStateAction } from "react";

import { triggerBrowserDownload } from "../utils/download";
import { shiftplanExportUrl } from "./shiftplansApi";
import { ShiftplansMarkup } from "./ShiftplansMarkup";
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

type ShiftplansAppShellProps = {
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
  readonly plans: readonly ShiftPlan[];
  readonly savingEntry: boolean;
  readonly selectedMachineIds: ReadonlySet<number>;
  readonly selectedPlanIndex: number;
  readonly showGenerateDrawer: boolean;
  readonly warnings: readonly ShiftplanWarning[];
  readonly writable: boolean;
  readonly onDeleteEntry: (entry: ShiftplanEntry) => Promise<void>;
  readonly onDeletePlan: () => Promise<void>;
  readonly onDialogSave: (entry: ShiftplanEntry, editDraft: ShiftplanEditDraft) => Promise<void>;
  readonly onDraftChange: Dispatch<SetStateAction<ShiftplanDraft>>;
  readonly onEditEntry: (entry: ShiftplanEntry) => void;
  readonly onGenerate: () => Promise<void>;
  readonly onGenerateClose: () => void;
  readonly onGenerateOpen: () => void;
  readonly onMachineToggle: (machineId: number, checked: boolean) => void;
  readonly onMoveEntryToEntry: (entryId: number, targetEntryId: number) => Promise<void>;
  readonly onMoveEntryToSlot: (entryId: number, targetDate: string, targetShift: string) => Promise<void>;
  readonly onPlanSelect: Dispatch<SetStateAction<number>>;
  readonly onPreview: () => Promise<void>;
  readonly onPublish: () => void;
  readonly setDialogEntry: Dispatch<SetStateAction<ShiftplanEntry | null>>;
  readonly setDialogMessage: Dispatch<SetStateAction<ShiftplansMessage>>;
};

/**
 * Render the Shiftplans markup with stable handler wiring.
 */
export function ShiftplansAppShell(props: ShiftplansAppShellProps): ReactNode {
  return (
    <div data-shiftplans-react-shell>
      <ShiftplansMarkup
        busyAction={props.busyAction}
        changelog={props.changelog}
        currentPlan={props.currentPlan}
        deletingEntry={props.deletingEntry}
        dialogEntry={props.dialogEntry}
        dialogMessage={props.dialogMessage}
        draft={props.draft}
        formMessage={props.formMessage}
        isAdmin={props.isAdmin}
        machines={props.machines}
        models={props.models}
        onDeleteEntry={props.onDeleteEntry}
        onDeletePlan={props.onDeletePlan}
        onDialogClose={() => props.setDialogEntry(null)}
        onDialogSave={props.onDialogSave}
        onDownload={() =>
          props.currentPlan?.id &&
          triggerBrowserDownload(shiftplanExportUrl(props.currentPlan.id), `${props.currentPlan.title || "schichtplan"}.xlsx`)
        }
        onDraftChange={props.onDraftChange}
        onEditEntry={(entry) => {
          props.setDialogMessage({ text: "" });
          props.onEditEntry(entry);
        }}
        onGenerate={props.onGenerate}
        onGenerateClose={props.onGenerateClose}
        onGenerateOpen={props.onGenerateOpen}
        onMachineToggle={props.onMachineToggle}
        onMoveEntryToEntry={props.onMoveEntryToEntry}
        onMoveEntryToSlot={props.onMoveEntryToSlot}
        onPlanSelect={props.onPlanSelect}
        onPreview={props.onPreview}
        onPrint={() => window.print()}
        onPublish={props.onPublish}
        plans={props.plans}
        savingEntry={props.savingEntry}
        selectedMachineIds={props.selectedMachineIds}
        selectedPlanIndex={props.selectedPlanIndex}
        showGenerateDrawer={props.showGenerateDrawer}
        warnings={props.warnings}
        writable={props.writable}
      />
    </div>
  );
}
