/**
 * Shift planning validation module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["validation"] = function attachShiftplansValidation(Shiftplans) {
    with (Shiftplans) {
      function renderStats(plan) {
        statsEl.hidden = false;
        statsBody.innerHTML = "";
        const emp = {};
        plan.entries.forEach((e) => {
          const id = e.employee ? e.employee.id : null;
          if (!id) return;
          if (!emp[id]) emp[id] = { name: e.employee.name, Frueh:0, Spaet:0, Nacht:0, Urlaub:0, h:0 };
          if (e.shift === "Frueh") emp[id].Frueh++;
          else if (e.shift === "Spaet") emp[id].Spaet++;
          else if (e.shift === "Nacht") emp[id].Nacht++;
          else if (e.shift === "Urlaub") emp[id].Urlaub++;
          if (e.start_time && e.end_time) emp[id].h += shiftH(e.start_time, e.end_time);
        });
        Object.values(emp).sort((a,b) => a.name.localeCompare(b.name)).forEach((s) => {
          const tr = document.createElement("tr");
          [s.name, s.Frueh, s.Spaet, s.Nacht, s.Urlaub, s.h.toFixed(1)+"h"].forEach((v, i) => {
            const td = i === 0 ? document.createElement("th") : document.createElement("td");
            if (i === 0) td.scope = "row";
            td.textContent = v;
            tr.appendChild(td);
          });
          statsBody.appendChild(tr);
        });
      }
      function shiftH(s, e) {
        const [sh,sm] = s.split(":").map(Number);
        const [eh,em] = e.split(":").map(Number);
        let d = (eh*60+em) - (sh*60+sm);
        if (d <= 0) d += 24*60;
        return d/60;
      }

      // ── Warnings ──────────────────────────────────────────────────────────────
      function showWarnings(list) {
        warnList.innerHTML = "";
        if (!list || !list.length) { warningsEl.hidden = true; return; }
        warnSummary.textContent = "⚠ Warnungen anzeigen (" + list.length + ")";
        list.forEach((w) => {
          const li = document.createElement("li");
          li.className = "panel-meta " + (w.severity === "critical" ? "text-error" : "text-warning");
          li.textContent = (w.severity === "critical" ? "⛔ " : "⚠ ") + w.message;
          warnList.appendChild(li);
        });
        warningsEl.hidden = false;
      }

      async function loadConflicts(planId) {
        try {
          const payload = await api(BASE + "/" + planId + "/conflicts");
          showWarnings(payload.conflicts || []);
        } catch (_) {
          showWarnings(currentPlan && currentPlan.warnings);
        }
      }

      // ── Changelog ─────────────────────────────────────────────────────────────
      async function loadChangelog(planId) {
        if (!isAdmin()) return;
        try {
          const logs = await api(BASE + "/" + planId + "/changelog");
          changelogBody.innerHTML = "";
          (logs || []).forEach((l) => {
            const tr = document.createElement("tr");
            [new Date(l.changed_at).toLocaleString("de-DE"), l.user||"–", l.action, l.field_name||"–", l.old_value||"–", l.new_value||"–"]
              .forEach((v) => { const td = document.createElement("td"); td.textContent = v; tr.appendChild(td); });
            changelogBody.appendChild(tr);
          });
        } catch (_) {}
      }
      Object.assign(Shiftplans, { renderStats, shiftH, showWarnings, loadConflicts, loadChangelog });
    }
  };
})();
