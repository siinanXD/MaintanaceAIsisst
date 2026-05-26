/**
 * Shift planning grid module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["grid"] = function attachShiftplansGrid(Shiftplans) {
    with (Shiftplans) {
      function renderGrid(plan) {
        tableWrap.hidden = false;
        thead.innerHTML  = "";
        tbody.innerHTML  = "";

        const start = new Date(plan.start_date + "T00:00:00");
        const dates = [];
        for (let i = 0; i < plan.days; i++) {
          const d = new Date(start);
          d.setDate(start.getDate() + i);
          dates.push(d);
        }

        // Index: shiftKey → dateStr → [entry]
        const idx = {};
        const usedShifts = new Set();
        plan.entries.forEach((e) => {
          const s = e.shift;
          usedShifts.add(s);
          if (!idx[s]) idx[s] = {};
          const ds = e.work_date;
          if (!idx[s][ds]) idx[s][ds] = [];
          idx[s][ds].push(e);
        });
        (plan.unassigned_slots || []).forEach((slot) => {
          const s = slot.shift;
          usedShifts.add(s);
          if (!idx[s]) idx[s] = {};
          if (!idx[s][slot.work_date]) idx[s][slot.work_date] = [];
          idx[s][slot.work_date].push({ ...slot, unassigned: true });
        });

        const activeShifts = SHIFT_ORDER.filter((s) => usedShifts.has(s));
        const canEdit = canWrite() && !plan.is_preview;

        // ── Header ──
        const hrow = document.createElement("tr");
        const th0 = document.createElement("th");
        th0.className = "sp-col-shift";
        th0.textContent = "Schicht";
        hrow.appendChild(th0);
        dates.forEach((d) => {
          const th = document.createElement("th");
          th.className = "sp-col-day";
          const dow = DAYS_DE[d.getDay()];
          const dd  = String(d.getDate()).padStart(2, "0");
          const mm  = String(d.getMonth() + 1).padStart(2, "0");
          th.innerHTML = "<span class='sp-dow'>" + dow + "</span><br><span class='sp-date'>" + dd + "." + mm + ".</span>";
          hrow.appendChild(th);
        });
        thead.appendChild(hrow);

        // ── Rows ──
        if (!activeShifts.length) {
          const tr = document.createElement("tr");
          const td = document.createElement("td");
          td.colSpan = dates.length + 1;
          td.className = "text-center";
          td.style.opacity = "0.5";
          td.textContent = "Keine Einträge im Plan.";
          tr.appendChild(td);
          tbody.appendChild(tr);
          return;
        }

        activeShifts.forEach((shiftKey) => {
          const tr = document.createElement("tr");

          // Schicht-Label (sticky)
          const thRow = document.createElement("th");
          thRow.className = "sp-col-shift sp-shift-label sp-shift-" + shiftKey.toLowerCase();
          thRow.textContent = SHIFT_LABEL[shiftKey] || shiftKey;
          tr.appendChild(thRow);

          // Day cells
          dates.forEach((d) => {
            const dateStr = localISO(d);
            const td = document.createElement("td");
            td.className = "sp-day-cell sp-cell-" + shiftKey.toLowerCase();

            if (canEdit) {
              td.addEventListener("dragover", (ev) => { ev.preventDefault(); td.classList.add("sp-drop-target"); });
              td.addEventListener("dragleave", () => td.classList.remove("sp-drop-target"));
              td.addEventListener("drop", async (ev) => {
                ev.preventDefault();
                td.classList.remove("sp-drop-target");
                const entryId = ev.dataTransfer.getData("entry_id");
                if (!entryId) return;
                try {
                  await api(BASE + "/entries/" + entryId + "/move", {
                    method: "PATCH",
                    body: JSON.stringify({ target_date: dateStr, target_shift: shiftKey }),
                  });
                  await loadPlans(currentPlan ? currentPlan.id : undefined);
                } catch (err) { alert("Fehler beim Verschieben: " + err.message); }
              });
            }
            const dayEntries = (idx[shiftKey] || {})[dateStr] || [];
            if (!dayEntries.length) {
              td.innerHTML = "<span class='sp-empty'>–</span>";
            } else {
              dayEntries.forEach((entry) => {
                const machineName = entry.machine ? entry.machine.name : null;
                const slotMachineName = machineName || entry.machine_name || null;
                const empName     = entry.unassigned
                  ? "Unbesetzt (" + (entry.missing || 1) + ")"
                  : (entry.employee ? entry.employee.name : "?");
                const chip = document.createElement(canEdit && !entry.unassigned ? "button" : "div");
                chip.className = "sp-chip" + (entry.unassigned ? " sp-unassigned" : "");
                if (canEdit && !entry.unassigned) {
                  chip.type = "button";
                  chip.setAttribute("aria-label", "Bearbeiten: " + empName);
                  chip.setAttribute("draggable", "true");
                  chip.dataset.entryId = entry.id;
                  chip.addEventListener("click", () => openDialog(entry));
                  chip.addEventListener("dragstart", (ev) => {
                    ev.dataTransfer.setData("entry_id", entry.id);
                    ev.dataTransfer.effectAllowed = "move";
                    chip.classList.add("sp-dragging");
                  });
                  chip.addEventListener("dragend", () => chip.classList.remove("sp-dragging"));
                  chip.addEventListener("dragover", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    if (ev.dataTransfer.getData("entry_id") !== String(entry.id))
                      chip.classList.add("sp-chip-drop-target");
                  });
                  chip.addEventListener("dragleave", () => chip.classList.remove("sp-chip-drop-target"));
                  chip.addEventListener("drop", async (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    chip.classList.remove("sp-chip-drop-target");
                    const entryId = ev.dataTransfer.getData("entry_id");
                    if (!entryId || entryId === String(entry.id)) return;
                    try {
                      await api(BASE + "/entries/" + entryId + "/move", {
                        method: "PATCH",
                        body: JSON.stringify({ target_entry_id: entry.id }),
                      });
                      await loadPlans(currentPlan ? currentPlan.id : undefined);
                    } catch (err) { alert("Fehler beim Tauschen: " + err.message); }
                  });
                }
                if (slotMachineName) {
                  chip.innerHTML =
                    "<span class='sp-machine'>" + slotMachineName + "</span>" +
                    "<span class='sp-emp'>" + empName + "</span>";
                } else {
                  chip.innerHTML = "<span class='sp-emp'>" + empName + "</span>";
                }
                td.appendChild(chip);
              });
            }
            tr.appendChild(td);
          });

          tbody.appendChild(tr);
        });
      }

      // ── Stats ─────────────────────────────────────────────────────────────────
      function openDialog(entry) {
        editEntryId = entry.id;
        dlgMsg.textContent = "";
        dlgShift.value = entry.shift;
        dlgStart.value = entry.start_time || "";
        dlgEnd.value   = entry.end_time   || "";
        dlgNotes.value = entry.notes      || "";
        dlgInfo.textContent = (entry.employee ? entry.employee.name : "") + " — " + entry.work_date;
        dlgTimes.hidden = ["Frei","Urlaub"].includes(entry.shift);
        dlgDelete.hidden = !isAdmin();
        dialog.showModal();
      }
      Object.assign(Shiftplans, { renderGrid, openDialog });
    }
  };
})();
