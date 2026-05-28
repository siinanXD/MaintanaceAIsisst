/**
 * Trigger a browser download for an existing URL.
 */
export function triggerBrowserDownload(url: string | undefined, filename: string | undefined): boolean {
  if (!url) return false;

  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "";
  document.body.appendChild(link);
  link.click();
  link.remove();
  return true;
}
