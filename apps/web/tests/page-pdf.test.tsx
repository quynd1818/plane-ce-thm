// @vitest-environment node
import path from "node:path";
import { Font, renderToBuffer } from "@react-pdf/renderer";
import { expect, it } from "vitest";
import { PDFDocument } from "@/components/editor/pdf/document";

it("renders a PDF with Vietnamese headings and table content using bundled fonts", async () => {
  // Node uses filesystem fonts; the app serves these same files as asset URLs.
  Font.clear();
  Font.register({ family: "Helvetica", src: "Helvetica" });
  Font.register({
    family: "Inter",
    fonts: [
      { src: path.resolve("app/assets/fonts/inter/regular.ttf"), fontWeight: "normal" },
      { src: path.resolve("app/assets/fonts/inter/semibold.ttf"), fontWeight: "semibold" },
      { src: path.resolve("app/assets/fonts/inter/bold.ttf"), fontWeight: "bold" },
    ],
  });
  const content =
    '<h1 class="page-title">Biên bản bàn giao</h1><p>Công trình đã hoàn thành.</p><table><tr><td>Hạng mục</td><td>Kết quả</td></tr><tr><td>Pháp lý</td><td>Đạt</td></tr></table>';
  const pdf = await renderToBuffer(<PDFDocument content={content} pageFormat="A4" />);
  expect(pdf.subarray(0, 5).toString()).toBe("%PDF-");
  expect(pdf.length).toBeGreaterThan(1000);
  expect(pdf.toString()).toContain("/FontFile2");
});
