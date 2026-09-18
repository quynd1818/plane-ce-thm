/** Keep Vietnamese titles while removing characters unsafe in filenames. */
export const pageExportFilename = (title: string) =>
  title
    .normalize("NFC")
    // oxlint-disable-next-line no-control-regex -- filenames must not contain control characters
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "-")
    .trim()
    .slice(0, 120)
    .replace(/[. ]+$/g, "") || "page";

export function pageExportHTML(title: string, content: string) {
  const heading = document.createElement("h1");
  heading.className = "page-title";
  heading.textContent = title;
  return heading.outerHTML + content;
}
