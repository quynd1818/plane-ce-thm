import { expect, it } from "vitest";
import JSZip from "jszip";
import { Packer } from "docx";
import { wordDocument } from "@/components/editor/word/document";
import { pageExportFilename, pageExportHTML } from "@/helpers/page-export";

it("preserves Vietnamese filenames and escapes the title for both PDF and Word", () => {
  expect(pageExportFilename("Biên bản bàn giao: tầng 1/2")).toBe("Biên bản bàn giao- tầng 1-2");
  expect(pageExportFilename("...")).toBe("page");
  const content = pageExportHTML("<img src=x onerror=bad()>", "<p>Body</p>");
  const doc = new DOMParser().parseFromString(content, "text/html");
  expect(doc.querySelector("img")).toBeNull();
  expect(doc.querySelector("h1")?.textContent).toBe("<img src=x onerror=bad()>");
});

it("exports a real DOCX containing Vietnamese headings, formatting, lists, tables and links", async () => {
  const { document, skippedImages } = wordDocument(
    pageExportHTML(
      "Biên bản bàn giao",
      `
    <h2>Nội dung nghiệm thu</h2><p><strong>Đã hoàn thành</strong> và <em>đã kiểm tra</em><br>Ngày bàn giao</p>
    <ol><li>Công việc một</li><li>Công việc hai<ul><li>Chi tiết</li></ul></li></ol>
    <table><tr><th>Hạng mục</th><th>Kết quả</th></tr><tr><td>Pháp lý</td><td>Đạt</td></tr></table>
    <p><a href="https://example.com/report">Biên bản gốc</a><a href="javascript:alert(1)">Unsafe link</a></p>
    <script>bad_script()</script>
  `
    )
  );
  const zip = await JSZip.loadAsync(await Packer.toBuffer(document));
  const xml = await zip.file("word/document.xml")!.async("string");
  const relations = await zip.file("word/_rels/document.xml.rels")!.async("string");
  expect(zip.file("[Content_Types].xml")).not.toBeNull();
  expect(xml).toContain("Biên bản bàn giao");
  expect(xml).toContain("Heading2");
  expect(xml).toContain("<w:b");
  expect(xml).toContain("<w:i");
  expect(xml).toContain("<w:tbl>");
  expect(xml).toContain("<w:numPr>");
  expect(xml).toContain("Pháp lý");
  expect(xml).not.toContain("bad_script");
  expect(relations).toContain("https://example.com/report");
  expect(relations).not.toContain("javascript:");
  expect(skippedImages).toBe(0);
});

it("embeds image bytes, and reports unavailable images without hiding their omission", async () => {
  const png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1ioAAAAASUVORK5CYII=";
  const { document, skippedImages } = wordDocument(
    `<p>Ảnh</p><img src="data:image/png;base64,${png}" width="10" height="10"><img src="https://unavailable.test/a.png" alt="Sơ đồ">`
  );
  const zip = await JSZip.loadAsync(await Packer.toBuffer(document));
  expect(Object.keys(zip.files).filter((name) => /word\/media\/.+\.png$/.test(name))).toHaveLength(1);
  expect(await zip.file("word/document.xml")!.async("string")).toContain("Sơ đồ");
  expect(skippedImages).toBe(1);
});
