(function () {
  window.maintenanceShared = window.maintenanceShared || {};

  /**
   * Create a badge element with text and classes.
   *
   * @param {string|number|null|undefined} text Badge label.
   * @param {string} className CSS classes.
   * @returns {HTMLSpanElement} Badge element.
   */
  function badge(text, className) {
    const element = document.createElement("span");
    element.className = className;
    element.textContent = text || "-";
    return element;
  }

  /**
   * Create a badge with an optional label formatter.
   *
   * @param {string|number|null|undefined} value Raw value.
   * @param {string} className CSS classes.
   * @param {Function} [labelFormatter] Label formatter.
   * @returns {HTMLSpanElement} Badge element.
   */
  function labeledBadge(value, className, labelFormatter) {
    return badge(labelFormatter ? labelFormatter(value) : value, className);
  }

  /**
   * Resolve the badge class for task priorities.
   *
   * @param {string} priority Task priority.
   * @returns {string} CSS class list.
   */
  function taskPriorityBadgeClass(priority) {
    if (priority === "urgent") return "badge badge-priority is-urgent";
    if (priority === "soon") return "badge badge-priority is-soon";
    return "badge badge-priority is-normal";
  }

  /**
   * Resolve the badge class for task statuses.
   *
   * @param {string} status Task status.
   * @returns {string} CSS class list.
   */
  function taskStatusBadgeClass(status) {
    if (status === "in_progress") return "badge badge-status is-progress";
    if (status === "done") return "badge badge-status is-done";
    if (status === "cancelled") return "badge badge-status is-cancelled";
    return "badge badge-status is-open";
  }

  /**
   * Resolve a generic status badge class.
   *
   * @param {string} status Status value.
   * @returns {string} CSS class list.
   */
  function genericStatusBadgeClass(status) {
    if (status === "active" || status === "done" || status === "approved") {
      return "badge badge-status is-done";
    }
    if (status === "pending" || status === "in_progress") {
      return "badge badge-status is-progress";
    }
    if (status === "cancelled" || status === "rejected" || status === "inactive") {
      return "badge badge-status is-cancelled";
    }
    return "badge badge-status is-open";
  }

  window.maintenanceShared.statusBadges = {
    badge,
    genericStatusBadgeClass,
    labeledBadge,
    taskPriorityBadgeClass,
    taskStatusBadgeClass
  };
})();
