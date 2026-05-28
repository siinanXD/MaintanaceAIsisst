/**
 * Dashboard shift calendar module.
 * Registers helpers on the current MaintenanceDashboardRuntime object.
 */
(function registerDashboardModule() {
  window.MaintenanceDashboardModules = window.MaintenanceDashboardModules || {};
  window.MaintenanceDashboardModules["shift-calendar"] = function attachDashboardShiftCalendar(Dashboard) {
    with (Dashboard) {
      function shiftTime(entry, fallbackStart, fallbackEnd) {
        return {
          start: entry && entry.start_time ? entry.start_time : fallbackStart,
          end: entry && entry.end_time ? entry.end_time : fallbackEnd
        };
      }

      function timeToMinutes(value) {
        const parts = String(value || "00:00").split(":");
        const hours = Math.max(0, Math.min(23, parseInt(parts[0], 10) || 0));
        const minutes = Math.max(0, Math.min(59, parseInt(parts[1], 10) || 0));
        return hours * 60 + minutes;
      }

      function timelineGeometry(start, end) {
        const startMinutes = timeToMinutes(start);
        let endMinutes = timeToMinutes(end);
        if (endMinutes <= startMinutes) endMinutes += 24 * 60;
        const visibleStart = Math.max(0, Math.min(startMinutes, 24 * 60));
        const visibleEnd = Math.max(0, Math.min(endMinutes, 24 * 60));
        return {
          left: (visibleStart / (24 * 60)) * 100,
          width: Math.max(((visibleEnd - visibleStart) / (24 * 60)) * 100, 2)
        };
      }

      function currentShiftKey(date) {
        const minutes = date.getHours() * 60 + date.getMinutes();
        if (minutes >= 6 * 60 && minutes < 14 * 60) return "Frueh";
        if (minutes >= 14 * 60 && minutes < 22 * 60) return "Spaet";
        return "Nacht";
      }

      function currentTimelinePercent(date) {
        const minutes = date.getHours() * 60 + date.getMinutes();
        return (minutes / (24 * 60)) * 100;
      }

      function timelineBarText(entry) {
        if (!entry) return "0 / 1";
        const machineName = entry.machine && entry.machine.name ? entry.machine.name : "";
        return machineName || "1 / 1";
      }

      function timelineRow(label, shiftKey, fallbackStart, fallbackEnd, variant, entry, activeShiftKey) {
        const rowElement = document.createElement("div");
        rowElement.className = "timeline-row";
        if (shiftKey === activeShiftKey) rowElement.classList.add("is-active");
        const title = document.createElement("strong");
        const time = shiftTime(entry, fallbackStart, fallbackEnd);
        const small = document.createElement("small");
        small.textContent = time.start + " - " + time.end;
        title.append(document.createTextNode(label), small);
        const bar = document.createElement("span");
        bar.className = "timeline-bar " + variant;
        bar.textContent = timelineBarText(entry);
        const geometry = timelineGeometry(time.start, time.end);
        bar.style.left = geometry.left.toFixed(2) + "%";
        bar.style.width = geometry.width.toFixed(2) + "%";
        rowElement.append(title, bar);
        return rowElement;
      }

      function renderShiftTimeline(calendar) {
        if (!shiftTimeline) return;
        shiftTimeline.innerHTML = "";
        const axis = document.createElement("div");
        axis.className = "timeline-axis";
        ["00", "04", "08", "12", "16", "20", "24"].forEach((label) => {
          const item = document.createElement("span");
          item.textContent = label;
          axis.appendChild(item);
        });
        shiftTimeline.appendChild(axis);
        if (calendar.message) {
          shiftTimeline.appendChild(emptyDashboardMessage(calendar.message));
          setDashboardText("[data-dashboard-shift-status]", "--");
          setDashboardText("[data-dashboard-shift-meta]", calendar.message);
          setProgress("[data-dashboard-shift-progress]", 8);
          return;
        }
        const now = new Date();
        const entries = Array.isArray(calendar.entries) ? calendar.entries : [];
        const today = todayIso();
        const todayEntries = entries.filter((entry) => entry.work_date === today && entry.shift !== "Frei");
        setDashboardText("[data-dashboard-shift-status]", todayEntries.length ? todayEntries.length + "/3" : "--");
        setDashboardText(
          "[data-dashboard-shift-meta]",
          todayEntries.length ? todayEntries.length + " Schichtbelegungen heute" : "Keine Schichtdaten heute"
        );
        setProgress("[data-dashboard-shift-progress]", todayEntries.length ? Math.min(100, (todayEntries.length / 3) * 100) : 12);
        const byShift = new Map(todayEntries.map((entry) => [entry.shift, entry]));
        const activeShiftKey = currentShiftKey(now);
        shiftTimeline.append(
          timelineRow("Frühschicht", "Frueh", "06:00", "14:00", "is-green", byShift.get("Frueh"), activeShiftKey),
          timelineRow("Spätschicht", "Spaet", "14:00", "22:00", "is-blue", byShift.get("Spaet"), activeShiftKey),
          timelineRow("Nachtschicht", "Nacht", "22:00", "06:00", "is-violet", byShift.get("Nacht"), activeShiftKey)
        );
        const marker = document.createElement("div");
        marker.className = "now-marker";
        marker.style.left = currentTimelinePercent(now).toFixed(2) + "%";
        marker.title = "Jetzt: " + now.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
        shiftTimeline.appendChild(marker);
      }

      async function setupDashboardCalendarFilter() {
        if (window.maintenanceDashboardReactShiftOwned === true) return;
        if (!shiftCalendarEmployee || !canView("employees")) return;
        try {
          const employees = listData(await api("/api/v1/employees?limit=200"));
          shiftCalendarEmployee.hidden = false;
          employees.forEach((employee) => {
            const option = document.createElement("option");
            option.value = String(employee.id);
            option.textContent = employee.name;
            shiftCalendarEmployee.appendChild(option);
          });
          if (!shiftCalendarEmployee.value && employees.length) {
            shiftCalendarEmployee.value = String(employees[0].id);
          }
        } catch (error) {
          shiftCalendarEmployee.hidden = true;
        }
      }

      async function loadShiftCalendar() {
        if (window.maintenanceDashboardReactShiftOwned === true) return;
        if (!shiftCalendar) return;
        const params = new URLSearchParams();
        params.set("days", "14");
        if (shiftCalendarEmployee && shiftCalendarEmployee.value) {
          params.set("employee_id", shiftCalendarEmployee.value);
        }
        try {
          const calendar = await api("/api/v1/shiftplans/calendar?" + params.toString());
          renderShiftCalendar(shiftCalendar, calendar);
          renderShiftTimeline(calendar);
          if (shiftCalendarMessage) {
            shiftCalendarMessage.textContent = calendar.employee
              ? "Kalender für " + calendar.employee.name
              : (calendar.message || "Schichtkalender");
            shiftCalendarMessage.classList.remove("is-error");
          }
        } catch (error) {
          renderShiftCalendar(shiftCalendar, { message: error.message, entries: [] });
          renderShiftTimeline({ message: error.message, entries: [] });
          if (shiftCalendarMessage) {
            shiftCalendarMessage.textContent = error.message;
            shiftCalendarMessage.classList.add("is-error");
          }
        }
      }

      function startDashboardShiftRealtime() {
        if (window.maintenanceDashboardReactShiftOwned === true) return;
        if (!shiftTimeline) return;
        window.setInterval(loadShiftCalendar, 60 * 1000);
      }

      Object.assign(Dashboard, { shiftTime, timeToMinutes, timelineGeometry, currentShiftKey, currentTimelinePercent, timelineBarText, timelineRow, renderShiftTimeline, setupDashboardCalendarFilter, loadShiftCalendar, startDashboardShiftRealtime });
    }
  };
})();
