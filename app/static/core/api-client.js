(function () {
  function token() {
    return window.maintenanceAuth ? window.maintenanceAuth.token() : null;
  }

  function handleExpiredSession() {
    if (window.maintenanceAuth && window.maintenanceAuth.clearSession) {
      window.maintenanceAuth.clearSession({ redirect: true });
    }
  }

  async function parseJson(response) {
    return response.json().catch(() => null);
  }

  async function request(path, options) {
    const requestOptions = options || {};
    const isFormData = typeof FormData !== "undefined" && requestOptions.body instanceof FormData;
    const headers = Object.assign(
      isFormData ? {} : { "Content-Type": "application/json" },
      requestOptions.headers
    );
    const authToken = token();
    if (authToken) headers.Authorization = "Bearer " + authToken;

    const response = await fetch(path, Object.assign({}, requestOptions, { headers }));
    if (response.status === 401 || response.status === 422) {
      handleExpiredSession();
      throw new Error("Sitzung abgelaufen. Bitte neu einloggen.");
    }
    if (response.status === 204) return null;
    const data = await parseJson(response);
    if (!response.ok) {
      throw new Error((data && (data.message || data.error)) || "API error");
    }
    return data;
  }

  async function downloadFile(url, filename) {
    const response = await fetch(url, {
      headers: { Authorization: "Bearer " + token() }
    });
    if (!response.ok) throw new Error("Download fehlgeschlagen");
    const blob = await response.blob();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(objectUrl);
  }

  window.maintenanceApi = {
    downloadFile,
    request
  };
})();
