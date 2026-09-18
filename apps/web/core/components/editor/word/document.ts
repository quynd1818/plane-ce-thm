import {
  Document,
  ExternalHyperlink,
  HeadingLevel,
  ImageRun,
  LevelFormat,
  Packer,
  Paragraph,
  Table,
  TableCell,
  TableRow,
  TextRun,
  UnderlineType,
  WidthType,
  type IRunOptions,
  type ParagraphChild,
  type INumberingOptions,
} from "docx";

type Block = Paragraph | Table;

/** Convert already-normalized editor HTML to real OOXML, entirely in the browser. */
export function wordDocument(htmlContent: string) {
  const html = new DOMParser().parseFromString(htmlContent, "text/html");
  const numbering: INumberingOptions["config"][number][] = [];
  let skippedImages = 0;
  const inline = (node: Node, formatting: IRunOptions = {}): ParagraphChild[] => {
    if (node.nodeType === Node.TEXT_NODE) return [new TextRun({ ...formatting, text: node.textContent ?? "" })];
    if (!(node instanceof Element)) return [];
    const tag = node.tagName.toLowerCase();
    if (["script", "style", "iframe", "object"].includes(tag)) return [];
    if (tag === "br") return [new TextRun({ break: 1 })];
    if (tag === "img") {
      const source = node.getAttribute("src") ?? "";
      const match = source.match(/^data:image\/(png|jpe?g|gif|bmp);base64,(.+)$/s);
      if (!match) {
        skippedImages++;
        return [new TextRun(`[Image: ${node.getAttribute("alt") || "not available"}]`)];
      }
      const width = Math.max(1, Number(node.getAttribute("width")) || 480);
      const height = Math.max(1, Number(node.getAttribute("height")) || 300);
      const scale = Math.min(1, 600 / width, 780 / height);
      return [
        new ImageRun({
          type: match[1] === "jpg" || match[1] === "jpeg" ? "jpg" : (match[1] as "png" | "gif" | "bmp"),
          data: Uint8Array.from(atob(match[2]), (char) => char.charCodeAt(0)),
          transformation: { width: width * scale, height: height * scale },
        }),
      ];
    }
    const style: IRunOptions = {
      ...formatting,
      ...(["strong", "b"].includes(tag) ? { bold: true } : {}),
      ...(["em", "i"].includes(tag) ? { italics: true } : {}),
      ...(tag === "u" ? { underline: { type: UnderlineType.SINGLE } } : {}),
      ...(["s", "del"].includes(tag) ? { strike: true } : {}),
      ...(tag === "code" || node.getAttribute("data-node-type")?.includes("code") ? { font: "Courier New" } : {}),
    };
    const children = Array.from(node.childNodes).flatMap((child) => inline(child, style));
    if (tag === "a") {
      const link = node.getAttribute("href") ?? "";
      if (/^(https?:|mailto:)/i.test(link)) return [new ExternalHyperlink({ link, children })];
    }
    return children;
  };
  const blocks = (nodes: Node[], depth = 0): Block[] => {
    const result: Block[] = [];
    let pending: ParagraphChild[] = [];
    const flush = () => {
      if (pending.length) {
        result.push(new Paragraph({ children: pending }));
        pending = [];
      }
    };
    for (const node of nodes) {
      if (!(node instanceof Element)) {
        if (node.textContent?.trim()) pending.push(...inline(node));
        continue;
      }
      const tag = node.tagName.toLowerCase();
      if (["script", "style", "iframe", "object"].includes(tag)) continue;
      if (tag === "table") {
        flush();
        const rows = Array.from(node.querySelectorAll("tr")).filter((row) => row.closest("table") === node);
        if (rows.length)
          result.push(
            new Table({
              width: { size: 100, type: WidthType.PERCENTAGE },
              rows: rows.map(
                (row) =>
                  new TableRow({
                    children: Array.from(row.children)
                      .filter((cell) => ["TD", "TH"].includes(cell.tagName))
                      .map((cell) => {
                        const content = blocks(Array.from(cell.childNodes));
                        if (!content.length || content.at(-1) instanceof Table) content.push(new Paragraph(""));
                        return new TableCell({
                          children: content,
                          columnSpan: Number(cell.getAttribute("colspan")) || 1,
                          rowSpan: Number(cell.getAttribute("rowspan")) || 1,
                        });
                      }),
                  })
              ),
            })
          );
      } else if (tag === "ul" || tag === "ol") {
        flush();
        const reference = `list-${numbering.length}`;
        numbering.push({
          reference,
          levels: [
            {
              level: 0,
              format: tag === "ol" ? LevelFormat.DECIMAL : LevelFormat.BULLET,
              text: tag === "ol" ? "%1." : "•",
              start: Number(node.getAttribute("start")) || 1,
              style: { paragraph: { indent: { left: 720 * (depth + 1), hanging: 360 } } },
            },
          ],
        });
        for (const li of Array.from(node.children)) {
          const content = Array.from(li.childNodes).filter(
            (child) => !(child instanceof Element && ["UL", "OL"].includes(child.tagName))
          );
          const checked = li.getAttribute("data-checked");
          result.push(
            new Paragraph({
              numbering: { reference, level: 0 },
              children: [
                ...(checked !== null ? [new TextRun(checked === "true" ? "☑ " : "☐ ")] : []),
                ...content.flatMap((child) => inline(child)),
              ],
            })
          );
          result.push(
            ...blocks(
              Array.from(li.children).filter((child) => ["UL", "OL"].includes(child.tagName)),
              depth + 1
            )
          );
        }
      } else if (/^h[1-6]$/.test(tag)) {
        flush();
        const levels = [
          HeadingLevel.HEADING_1,
          HeadingLevel.HEADING_2,
          HeadingLevel.HEADING_3,
          HeadingLevel.HEADING_4,
          HeadingLevel.HEADING_5,
          HeadingLevel.HEADING_6,
        ];
        result.push(new Paragraph({ heading: levels[Number(tag[1]) - 1], children: inline(node), keepNext: true }));
      } else if (["div", "section", "article", "blockquote"].includes(tag)) {
        flush();
        result.push(...blocks(Array.from(node.childNodes)));
      } else if (["p", "pre"].includes(tag)) {
        flush();
        result.push(new Paragraph({ children: inline(node), spacing: { after: 120 } }));
      } else if (tag === "hr") {
        flush();
        result.push(new Paragraph("────────────────────────"));
      } else pending.push(...inline(node));
    }
    flush();
    return result;
  };
  const children = blocks(Array.from(html.body.childNodes));
  const document = new Document({
    styles: { default: { document: { run: { font: "Arial", size: 22 }, paragraph: { spacing: { after: 120 } } } } },
    numbering: { config: numbering },
    sections: [{ properties: { page: { size: { width: 11906, height: 16838 } } }, children }],
  });
  return { document, skippedImages };
}

export async function exportWord(content: string) {
  const parsed = new DOMParser().parseFromString(content, "text/html");
  await Promise.all(
    Array.from(parsed.querySelectorAll("img")).map(async (element) => {
      if (!element.src.startsWith("data:image/")) return;
      const image = new Image();
      image.src = element.src;
      try {
        await image.decode();
        const width = Number(element.getAttribute("width")) || parseFloat(element.style.width) || image.naturalWidth;
        const height =
          Number(element.getAttribute("height")) ||
          parseFloat(element.style.height) ||
          (image.naturalHeight * width) / image.naturalWidth;
        element.setAttribute("width", String(width));
        element.setAttribute("height", String(height));
      } catch {
        // Invalid data will be reported by the export handler instead of silently claiming success.
        throw new Error("An image could not be decoded. Try exporting without images.");
      }
    })
  );
  const { document, skippedImages } = wordDocument(parsed.body.innerHTML);
  return { blob: await Packer.toBlob(document), skippedImages };
}
