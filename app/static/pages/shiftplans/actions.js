/**
 * Shift planning actions module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["actions"] = function attachShiftplansActions(Shiftplans) {
    with (Shiftplans) {
      function bindShiftplanActions() {
      dlgShift.addEventListener("change", () => {
        const isWork = !["Frei","Urlaub"].includes(dlgShift.value);
        dlgTimes.hidden = !isWork;
        if (isWork && SHIFT_WINDOWS[dlgShift.value]) {
          dlgStart.value = SHIFT_WINDOWS[dlgShift.value][0];
          dlgEnd.value   = SHIFT_WINDOWS[dlgShift.value][1];
        }
      });

      dlgSave.addEventListener("click", async () => {
        if (!editEntryId) return;
        dlgMsg.textContent = "Wird gespeichert...";
        dlgSave.disabled = true;
        const payload = { shift: dlgShift.value, notes: dlgNotes.value };
        if (!["Frei","Urlaub"].includes(dlgShift.value)) {
          payload.start_time = dlgStart.value;
          payload.end_time   = dlgEnd.value;
        }
        try {
          await api(BASE + "/entries/" + editEntryId, { method: "PATCH", body: JSON.stringify(payload) });
          dialog.close();
          const pid = currentPlan ? currentPlan.id : undefined;
          await loadPlans(pid);
        } catch (err) { dlgMsg.textContent = err.message; }
        finally { dlgSave.disabled = false; }
      });

      dlgDelete.addEventListener("click", async () => {
        if (!editEntryId || !confirm("Eintrag wirklich löschen?")) return;
        dlgDelete.disabled = true;
        try {
          await api(BASE + "/entries/" + editEntryId, { method: "DELETE" });
          dialog.close();
          const pid = currentPlan ? currentPlan.id : undefined;
          await loadPlans(pid);
        } catch (err) { dlgMsg.textContent = err.message; }
        finally { dlgDelete.disabled = false; }
      });

      dlgCancel.addEventListener("click", () => dialog.close());
      dialog.addEventListener("keydown", (e) => { if (e.key === "Escape") dialog.close(); });

      // Plan selector.
      planSelect.addEventListener("change", () => {
        const p = allPlans[parseInt(planSelect.value, 10)];
        if (p) renderPlan(p);
      });

      // Plan löschen.
      deleteBtn.addEventListener("click", async () => {
        if (!currentPlan || !confirm("Plan \"" + currentPlan.title + "\" wirklich löschen?")) return;
        deleteBtn.disabled = true;
        try {
          await api(BASE + "/" + currentPlan.id, { method: "DELETE" });
          currentPlan = null;
          await loadPlans();
        } catch (err) { alert(err.message); }
        finally { deleteBtn.disabled = false; }
      });

      // Publish plan.
      publishBtn.addEventListener("click", async () => {
        if (!currentPlan) return;
        const willPublish = currentPlan.status !== "published";
        if (willPublish) {
          try {
            const validation = await api(BASE + "/" + currentPlan.id + "/conflicts");
            const critical = validation.summary ? validation.summary.critical : 0;
            if (critical > 0 && !confirm("Der Plan hat " + critical + " kritische Konflikte. Trotzdem veroeffentlichen?")) {
              showWarnings(validation.conflicts || []);
              return;
            }
          } catch (_) {}
        }
        const msg = willPublish
          ? "Plan \"" + currentPlan.title + "\" veröffentlichen? Mitarbeiter können ihn dann sehen."
          : "Plan zurück auf Entwurf setzen? Er wird für Mitarbeiter ausgeblendet.";
        if (!confirm(msg)) return;
        publishBtn.disabled = true;
        try {
          const updated = await api(BASE + "/" + currentPlan.id + "/publish", { method: "PATCH" });
          await loadPlans(updated.id || currentPlan.id);
        } catch (err) { alert("Fehler: " + err.message); }
        finally { publishBtn.disabled = false; }
      });

      // Print / CSV.
      printBtn.addEventListener("click", () => window.print());

      csvBtn.addEventListener("click", () => {
        if (!currentPlan) return;
        const a = document.createElement("a");
        a.href = BASE + "/" + currentPlan.id + "/export.xlsx";
        a.download = (currentPlan.title||"schichtplan") + ".xlsx";
        a.click();
      });
      }

      // Form submit.
      function buildGenerationPayload() {
        const dept  = document.getElementById("sp-department").value;
        const start = document.getElementById("sp-start").value;
        const model = selectedShiftModel();
        const machineIds = selectedMachineIds();
        if (!dept) throw new Error("Bitte Abteilung w\u00e4hlen.");
        if (!start) throw new Error("Bitte Startdatum angeben.");
        if (!model) throw new Error("Bitte ein Schichtmodell w\u00e4hlen.");
        if (!machineIds.length) throw new Error("Bitte mindestens eine Maschine ausw\u00e4hlen.");
        const vacText = document.getElementById("sp-vacations").value || "";
        const vacations = vacText.split("\n").flatMap((line) => {
          const parts = line.split(",").map((s) => s.trim());
          if (parts.length >= 2 && parts[0] && parts[1]) {
            return [{ employee_id: parseInt(parts[0], 10), date: parts[1], notes: parts[2]||"" }];
          }
          return [];
        });
        return {
          department:   dept,
          title:        document.getElementById("sp-title").value,
          start_date:   start,
          days:         parseInt(document.getElementById("sp-days").value||"7", 10),
          shift_model_key: model.key,
          machine_ids:   machineIds,
          rhythm:       document.getElementById("sp-rhythm").value || model.display_name || model.key,
          preferences:  { text: document.getElementById("sp-preferences").value || "" },
          vacations,
        };
      }

      async function submitShiftPlanPreview() {
        let payload;
        try {
          payload = buildGenerationPayload();
        } catch (err) {
          spMsg.textContent = err.message;
          return;
        }
        previewBtn.disabled = true;
        spMsg.textContent = "Vorschau wird erstellt...";
        try {
          const result = await api(BASE + "/preview", { method: "POST", body: JSON.stringify(payload) });
          spMsg.textContent = "Vorschau erstellt. Noch nicht gespeichert.";
          currentPlan = result;
          renderPlan(result);
          showWarnings(result && result.warnings);
        } catch (err) {
          spMsg.textContent = "Fehler: " + err.message;
          if (err.payload && err.payload.warnings) showWarnings(err.payload.warnings);
        } finally {
          previewBtn.disabled = false;
        }
      }

      if (previewBtn) {
        previewBtn.addEventListener("click", submitShiftPlanPreview);
      }

      async function submitShiftPlanGeneration() {
        let payload;
        try {
          payload = buildGenerationPayload();
        } catch (err) {
          spMsg.textContent = err.message;
          return;
        }
        submitBtn.disabled = true;
        spMsg.textContent  = "Plan wird generiert...";
        try {
          const result = await api(BASE + "/generate", { method: "POST", body: JSON.stringify(payload) });
          spMsg.textContent = "Plan erfolgreich generiert.";
          showWarnings(result && result.warnings);
          if (result && result.entries) {
            currentPlan = result;
            renderPlan(result);
          }
          await loadPlans(result && result.id, result);
        } catch (err) {
          spMsg.textContent = "Fehler: " + err.message;
          if (err.payload && err.payload.warnings) showWarnings(err.payload.warnings);
        } finally {
          submitBtn.disabled = false;
        }
      }

      if (submitBtn) {
        submitBtn.addEventListener("click", submitShiftPlanGeneration);
      }


      function setDefaultStartDate() {
        const startInput = document.getElementById("sp-start");
        if (startInput && !startInput.value) startInput.value = new Date().toISOString().slice(0,10);
      }

      async function initializeShiftplansPage() {
        setDefaultStartDate();
        if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();

        const currentToken = token();
        if (!currentToken) {
          initializedToken = null;
          return null;
        }
        if (initializationPromise) return initializationPromise;
        if (initializedToken === currentToken) return null;

        initializationPromise = Promise.all([
          loadShiftModels(),
          loadMachines(),
          loadPlans(),
        ]).finally(() => {
          initializedToken = currentToken;
          initializationPromise = null;
        });
        return initializationPromise;
      }

      function scheduleShiftplansInitialization() {
        initializeShiftplansPage().catch((err) => {
          if (spMsg) spMsg.textContent = "Schichtplanung konnte nicht geladen werden: " + err.message;
          console.warn(err);
        });
      }
      Object.assign(Shiftplans, { bindShiftplanActions, buildGenerationPayload, submitShiftPlanPreview, submitShiftPlanGeneration, setDefaultStartDate, initializeShiftplansPage, scheduleShiftplansInitialization });
      window.addEventListener("maintenance-auth-ready", scheduleShiftplansInitialization);
      window.addEventListener("maintenance-auth-changed", () => {
        initializedToken = null;
        scheduleShiftplansInitialization();
      });
      if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", scheduleShiftplansInitialization, { once: true });
      } else {
        scheduleShiftplansInitialization();
      }
    }
  };
})();

