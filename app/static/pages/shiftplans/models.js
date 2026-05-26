/**
 * Shift planning models module.
 * Registers helpers on the current MaintenanceShiftplansRuntime object.
 */
(function registerShiftplansModule() {
  window.MaintenanceShiftplansModules = window.MaintenanceShiftplansModules || {};
  window.MaintenanceShiftplansModules["models"] = function attachShiftplansModels(Shiftplans) {
    with (Shiftplans) {
      function beginnerModelLabel(model) {
        const labels = {
          one_shift: "Tagschicht",
          two_shift: "2-Schicht Fr\u00fch/Sp\u00e4t",
          three_shift: "3-Schicht Fr\u00fch/Sp\u00e4t/Nacht",
          teilkonti: "Teilkonti",
          vollkonti_4: "Vollkonti 4-Schicht",
          vollkonti_5: "Vollkonti 5-Schicht",
        };
        return labels[model.key] || model.display_name || model.name || model.key;
      }

      function formatShiftWindow(shift) {
        const name = shift.label || shift.name || shift.key;
        return name + " " + shift.start_time + "-" + shift.end_time;
      }

      function shiftSummary(model) {
        if (model.shifts_summary) return model.shifts_summary;
        return (model.shifts || []).map(formatShiftWindow).join(", ");
      }

      function rotationLabel(value) {
        if (value === "forward") return "Vorw\u00e4rtsrotation Fr\u00fch \u2192 Sp\u00e4t \u2192 Nacht";
        if (value === "fixed") return "Feste Tagschicht";
        return value || "-";
      }

      function updateHiddenRhythm(model) {
        const rhythmInput = document.getElementById("sp-rhythm");
        if (!rhythmInput) return;
        rhythmInput.value = model ? (model.display_name || model.name || model.key) : "";
      }

      function renderShiftModelPreview(model) {
        updateHiddenRhythm(model);
        if (!shiftModelPreview) return;
        if (!model) {
          shiftModelPreview.hidden = true;
          return;
        }
        shiftModelTitle.textContent = beginnerModelLabel(model);
        shiftModelDescription.textContent = model.description || "";
        shiftModelShifts.textContent = shiftSummary(model);
        shiftModelTeamCount.textContent = String(model.team_count || "-");
        shiftModelWeekend.textContent = model.weekend_label || (
          model.weekend_operation ? "Wochenendbetrieb aktiv" : "Montag bis Freitag"
        );
        shiftModelRotation.textContent = model.rotation_label || rotationLabel(model.rotation_direction);
        shiftModelRest.textContent = (model.recommended_rest_hours || 11) + " Stunden empfohlen";
        shiftModelPreview.hidden = false;
      }

      function selectedShiftModel() {
        if (!shiftModelSelect || !shiftModelSelect.value) return null;
        if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();
        const cachedModel = shiftModels.find((model) => model.key === shiftModelSelect.value);
        if (cachedModel) return cachedModel;
        const selectedOption = shiftModelSelect.options[shiftModelSelect.selectedIndex];
        if (!selectedOption || !selectedOption.value) return null;
        return {
          key: selectedOption.value,
          display_name: selectedOption.dataset.displayName || selectedOption.textContent,
          name: selectedOption.dataset.displayName || selectedOption.textContent,
          description: selectedOption.dataset.description || "",
          shifts_summary: selectedOption.dataset.shiftsSummary || "",
          team_count: Number(selectedOption.dataset.teamCount || 0),
          weekend_operation: selectedOption.dataset.weekendOperation === "true",
          weekend_label: selectedOption.dataset.weekendLabel || "",
          rotation_direction: selectedOption.dataset.rotationDirection || "",
          rotation_label: selectedOption.dataset.rotationLabel || "",
          recommended_rest_hours: Number(selectedOption.dataset.restHours || 11),
        };
      }

      function readShiftModelsFromSelect() {
        if (!shiftModelSelect) return [];
        return Array.from(shiftModelSelect.options)
          .filter((option) => option.value)
          .map((option) => ({
            key: option.value,
            display_name: option.dataset.displayName || option.textContent,
            name: option.dataset.displayName || option.textContent,
            description: option.dataset.description || "",
            shifts_summary: option.dataset.shiftsSummary || "",
            team_count: Number(option.dataset.teamCount || 0),
            weekend_operation: option.dataset.weekendOperation === "true",
            weekend_label: option.dataset.weekendLabel || "",
            rotation_direction: option.dataset.rotationDirection || "",
            rotation_label: option.dataset.rotationLabel || "",
            recommended_rest_hours: Number(option.dataset.restHours || 11),
          }));
      }

      function populateShiftModelSelect(models) {
        if (!shiftModelSelect) return;
        const previousValue = shiftModelSelect.value;
        shiftModelSelect.innerHTML = "";
        const placeholder = document.createElement("option");
        placeholder.value = "";
        placeholder.disabled = true;
        placeholder.textContent = "Bitte Schichtmodell w\u00e4hlen";
        shiftModelSelect.appendChild(placeholder);
        models.forEach((model) => {
          const option = document.createElement("option");
          option.value = model.key;
          option.textContent = beginnerModelLabel(model);
          shiftModelSelect.appendChild(option);
        });
        if (previousValue && models.some((model) => model.key === previousValue)) {
          shiftModelSelect.value = previousValue;
        } else {
          shiftModelSelect.value = "";
        }
        renderShiftModelPreview(selectedShiftModel());
      }

      async function loadShiftModels() {
        if (!shiftModelSelect) return [];
        if (!shiftModels.length) shiftModels = readShiftModelsFromSelect();
        if (!token()) return shiftModels;
        if (shiftModelsLoadPromise) return shiftModelsLoadPromise;
        shiftModelsLoadPromise = api(BASE + "/models")
          .then((models) => {
            shiftModels = models;
            populateShiftModelSelect(shiftModels);
            return shiftModels;
          })
          .catch((err) => {
            if (!shiftModels.length) {
              shiftModelSelect.innerHTML = "<option value=''>Modelle konnten nicht geladen werden</option>";
            }
            if (spMsg) spMsg.textContent = "Schichtmodelle konnten nicht geladen werden: " + err.message;
            return shiftModels;
          })
          .finally(() => {
            shiftModelsLoadPromise = null;
          });
        return shiftModelsLoadPromise;
      }

      if (shiftModelSelect) {
        shiftModelSelect.addEventListener("change", () => {
          renderShiftModelPreview(selectedShiftModel());
          if (spMsg) spMsg.textContent = "";
        });
      }
      Object.assign(Shiftplans, { beginnerModelLabel, formatShiftWindow, shiftSummary, rotationLabel, updateHiddenRhythm, renderShiftModelPreview, selectedShiftModel, readShiftModelsFromSelect, populateShiftModelSelect, loadShiftModels });
    }
  };
})();
