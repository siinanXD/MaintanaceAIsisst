/**
 * Shift planning plans module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["plans"] = function attachShiftplansPlans(Shiftplans) {
    with (Shiftplans) {
      async function loadPlans(selectId, fallbackPlan) {
        if (!token()) return;
        try {
          const res = await fetch(BASE, { headers: authHdr() });
          if (!res.ok) {
            const body = await res.json().catch(() => ({}));
            emptyMsg.textContent = "Fehler beim Laden der Pläne: " + (body.message || res.status);
            emptyMsg.hidden = false;
            return;
          }
          allPlans = await res.json();
        } catch (err) {
          allPlans = [];
          emptyMsg.textContent = "Netzwerkfehler: " + err.message;
          emptyMsg.hidden = false;
        }
        if (
          fallbackPlan &&
          selectId !== undefined &&
          !allPlans.some((plan) => plan.id === selectId)
        ) {
          allPlans.unshift(fallbackPlan);
        }

        if (!allPlans.length) {
          emptyMsg.hidden   = false;
          tableWrap.hidden  = true;
          spSelector.hidden = true;
          statsEl.hidden    = true;
          warningsEl.hidden = true;
          printBtn.hidden   = true;
          csvBtn.hidden     = true;
          publishBtn.hidden = true;
          deleteWrap.hidden = true;
          return;
        }

        emptyMsg.hidden   = true;
        spSelector.hidden = false;
        printBtn.hidden   = false;
        csvBtn.hidden     = false;

        planSelect.innerHTML = "";
        allPlans.forEach((p, i) => {
          const opt = document.createElement("option");
          opt.value = i;
          const statusMark = p.status === "published" ? " ✓" : " [Entwurf]";
          opt.textContent = p.title + (p.department ? " [" + p.department + "]" : "") + statusMark;
          planSelect.appendChild(opt);
        });

        const idx = selectedPlanIndex(selectId);
        planSelect.value = idx;
        renderPlan(allPlans[planSelect.value] || allPlans[0]);
      }

      function selectedPlanIndex(selectId) {
        if (selectId !== undefined) {
          const exactIndex = allPlans.findIndex((plan) => plan.id === selectId);
          if (exactIndex >= 0) return exactIndex;
        }
        const firstFilledIndex = allPlans.findIndex(
          (plan) => Array.isArray(plan.entries) && plan.entries.length > 0
        );
        return firstFilledIndex >= 0 ? firstFilledIndex : 0;
      }

      function renderPlan(plan) {
        currentPlan = plan;
        renderGrid(plan);
        renderStats(plan);
        if (plan.id) {
          loadConflicts(plan.id);
        } else {
          showWarnings(plan.warnings || []);
        }
        const admin = isAdmin();
        deleteWrap.hidden = !admin || !plan.id;
        if (changelogEl) changelogEl.hidden = !admin || !plan.id;
        if (admin && plan.id) loadChangelog(plan.id);

        // Publish button (admin only)
        publishBtn.hidden = !admin || !plan.id;
        if (admin) {
          const published = plan.status === "published";
          publishBtn.textContent = published ? "↩ Zurück zu Entwurf" : "✓ Veröffentlichen";
          publishBtn.className   = "btn btn-sm no-print " +
            (published ? "btn-warning" : "btn-success");
        }

        // Status-Badge
        statusBadge.hidden = false;
        if (plan.status === "preview") {
          statusBadge.textContent = "Vorschau";
          statusBadge.className   = "badge badge-info";
        } else if (plan.status === "published") {
          statusBadge.textContent = "✓ Veröffentlicht";
          statusBadge.className   = "badge badge-success";
        } else {
          statusBadge.textContent = "Entwurf";
          statusBadge.className   = "badge badge-ghost";
        }

        // Update print header
        printTitle.textContent = plan.title || "Schichtplan";
        printMeta.textContent  = "Abteilung: " + (plan.department || "–") +
          " | " + plan.start_date + " | " + plan.days + " Tage" +
          (plan.status === "published" ? " | ✓ Veröffentlicht" : " | Entwurf");
      }

      // ── Excel-Grid ────────────────────────────────────────────────────────────
      // Rows = Schichttyp, Cols = day, Cell = machine+employee list
      Object.assign(Shiftplans, { loadPlans, selectedPlanIndex, renderPlan });
    }
  };
})();
