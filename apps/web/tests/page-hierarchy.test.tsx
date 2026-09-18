import { describe, expect, it, vi } from "vitest";
import { descendantPageIds, pageTreeRows } from "@/helpers/page-hierarchy";
import { BasePage } from "@/store/pages/base-page";
import type { TBasePageServices } from "@/store/pages/base-page";
import type { TPage } from "@plane/types";
import type { RootStore } from "@/store/root.store";

const pages = [{ id: "root" }, { id: "child", parent: "root" }, { id: "grandchild", parent: "child" }, { id: "other" }];

describe("page hierarchy", () => {
  it("nests pages in stable order", () => {
    expect(pageTreeRows(pages).map(({ id, depth }) => [id, depth])).toEqual([
      ["root", 0],
      ["child", 1],
      ["grandchild", 2],
      ["other", 0],
    ]);
  });
  it("hides all descendants of a collapsed parent", () => {
    expect(pageTreeRows(pages, new Set(["root"])).map(({ id }) => id)).toEqual(["root", "other"]);
  });
  it("shows matching children when their parent is hidden by filters or permissions", () => {
    expect(pageTreeRows([{ id: "child", parent: "unavailable" }])).toEqual([
      { id: "child", depth: 0, hasChildren: false },
    ]);
  });
  it("handles legacy cycles without looping or dropping pages", () => {
    expect(
      pageTreeRows([
        { id: "a", parent: "b" },
        { id: "b", parent: "a" },
      ])
    ).toHaveLength(2);
  });
  it("excludes the current page and all descendants as parent destinations", () => {
    expect([...descendantPageIds(pages, "root")]).toEqual(["root", "child", "grandchild"]);
  });
});

it("sends the new parent, including null, instead of the old page snapshot", async () => {
  const update = vi.fn().mockResolvedValue({});
  const page = new BasePage(
    {} as RootStore,
    { id: "child", parent: "old" } as TPage,
    { update } as unknown as TBasePageServices
  );
  try {
    await page.update({ parent: "new" });
    expect(update).toHaveBeenLastCalledWith({ parent: "new" });
    expect(page.parent).toBe("new");
    await page.update({ parent: null });
    expect(update).toHaveBeenLastCalledWith({ parent: null });
    expect(page.parent).toBeNull();
    update.mockRejectedValueOnce(new Error("Forbidden"));
    await expect(page.update({ parent: "denied" })).rejects.toThrow();
    expect(page.parent).toBeNull();
  } finally {
    page.cleanup();
  }
});
