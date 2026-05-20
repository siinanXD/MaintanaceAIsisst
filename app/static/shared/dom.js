(function () {
  window.maintenanceShared = window.maintenanceShared || {};

  /**
   * Return the first element matching a selector within the given root.
   *
   * @param {string} selector CSS selector to resolve.
   * @param {ParentNode} [root=document] Root node for the lookup.
   * @returns {Element|null} Matching element or null.
   */
  function qs(selector, root = document) {
    return root.querySelector(selector);
  }

  /**
   * Return all elements matching a selector within the given root.
   *
   * @param {string} selector CSS selector to resolve.
   * @param {ParentNode} [root=document] Root node for the lookup.
   * @returns {Element[]} Matching elements.
   */
  function qsa(selector, root = document) {
    return Array.from(root.querySelectorAll(selector));
  }

  /**
   * Remove all child nodes from an element.
   *
   * @param {Element|null} element Element to clear.
   * @returns {Element|null} The cleared element or null.
   */
  function clear(element) {
    if (!element) return null;
    element.replaceChildren();
    return element;
  }

  /**
   * Append multiple children or text values to a parent element.
   *
   * @param {Element} parent Parent element.
   * @param {...(Node|string|number|null|undefined)} children Children to append.
   * @returns {Element} The parent element.
   */
  function appendChildren(parent, ...children) {
    children.forEach((child) => {
      if (child === null || child === undefined) return;
      parent.appendChild(child instanceof Node ? child : document.createTextNode(String(child)));
    });
    return parent;
  }

  /**
   * Create an element with optional class and text content.
   *
   * @param {string} tagName Element tag name.
   * @param {object} [options] Element options.
   * @param {string} [options.className] CSS class name.
   * @param {string|number} [options.textContent] Text content.
   * @returns {HTMLElement} Created element.
   */
  function text(tagName, options = {}) {
    const element = document.createElement(tagName);
    if (options.className) element.className = options.className;
    if (options.textContent !== undefined) element.textContent = String(options.textContent);
    return element;
  }

  /**
   * Normalize common paginated API envelopes to an item array.
   *
   * @param {unknown} result API response payload.
   * @returns {Array} Extracted item array.
   */
  function listData(result) {
    if (Array.isArray(result)) return result;
    if (result && Array.isArray(result.data)) return result.data;
    if (result && result.data && Array.isArray(result.data.items)) return result.data.items;
    if (result && Array.isArray(result.items)) return result.items;
    return [];
  }

  /**
   * Read a total count from a paginated API response.
   *
   * @param {object|null|undefined} result API response payload.
   * @param {Array|null|undefined} fallbackItems Items used when pagination is absent.
   * @returns {number} Total item count.
   */
  function paginationTotal(result, fallbackItems) {
    const pagination = result && (result.pagination || (result.data && result.data.pagination));
    if (pagination && Number.isFinite(Number(pagination.total))) return Number(pagination.total);
    return Array.isArray(fallbackItems) ? fallbackItems.length : 0;
  }

  /**
   * Create a table row from primitive values or nodes.
   *
   * @param {Array<Node|string|number|null|undefined>} cells Cell values.
   * @returns {HTMLTableRowElement} Created table row.
   */
  function row(cells) {
    const tr = document.createElement("tr");
    cells.forEach((cell) => {
      const td = document.createElement("td");
      if (cell instanceof Node) td.appendChild(cell);
      else td.textContent = cell || "-";
      tr.appendChild(td);
    });
    return tr;
  }

  window.maintenanceShared.dom = {
    appendChildren,
    clear,
    listData,
    paginationTotal,
    qs,
    qsa,
    row,
    text
  };
})();
