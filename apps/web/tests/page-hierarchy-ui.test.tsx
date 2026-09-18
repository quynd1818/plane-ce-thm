import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { PageHierarchy } from "@/components/pages/editor/page-hierarchy";
import { PagesListRoot } from "@/components/pages/list/root";
import type { EPageStoreType } from "@/hooks/store";
import type { TPageInstance } from "@/store/pages/base-page";

const state = vi.hoisted(() => ({
  pages: [
    { id: "root", name: "Root", parent: null as string | null, isContentEditable: true, access: 0 },
    { id: "child", name: "Child", parent: "root", isContentEditable: true, access: 0 },
    { id: "other", name: "Other", parent: null, isContentEditable: true, access: 0 },
  ],
  update: vi.fn(),
  mutate: vi.fn(),
}));
vi.mock("@/hooks/store", () => ({
  usePageStore: () => ({
    getCurrentProjectFilteredPageIdsByTab: () => state.pages.map((page) => page.id),
    getPageById: (id: string) => state.pages.find((page) => page.id === id),
    canCurrentUserCreatePage: true,
  }),
}));
vi.mock("swr", () => ({ default: () => ({ data: state.pages, mutate: state.mutate }) }));
vi.mock("@plane/propel/button", () => ({
  Button: ({ children, onClick }: { children: React.ReactNode; onClick: () => void }) => (
    <button onClick={onClick}>{children}</button>
  ),
}));
vi.mock("@plane/propel/toast", () => ({ TOAST_TYPE: { ERROR: "error" }, setToast: vi.fn() }));
vi.mock("@plane/utils", () => ({ getPageName: (name: string) => name || "Untitled" }));
vi.mock("@/components/pages/modals/create-page-modal", () => ({
  CreatePageModal: ({ parentId, isModalOpen }: { parentId: string; isModalOpen: boolean }) =>
    isModalOpen ? <div role="dialog">Parent: {parentId}</div> : null,
}));
vi.mock("@/components/core/list", () => ({
  ListLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));
vi.mock("@/components/pages/list/block", () => ({
  PageListBlock: ({ pageId }: { pageId: string }) => <span data-page={pageId}>{pageId}</span>,
}));
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.clearAllMocks();
  state.update.mockResolvedValue({});
  container = document.createElement("div");
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.unstubAllGlobals();
});

it("opens child creation with the selected parent and excludes descendants from moving", async () => {
  const page = { ...state.pages[0], update: state.update } as unknown as TPageInstance;
  await act(async () =>
    root.render(
      <MemoryRouter>
        <PageHierarchy page={page} storeType={"project" as EPageStoreType} projectId="project" workspaceSlug="thm" />
      </MemoryRouter>
    )
  );
  expect(Array.from(container.querySelectorAll("option")).map((option) => option.value)).toEqual(["", "other"]);
  await act(async () => container.querySelector("button")!.click());
  expect(container.querySelector('[role="dialog"]')?.textContent).toBe("Parent: root");
  const select = container.querySelector("select")!;
  await act(async () => {
    select.value = "other";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(state.update).toHaveBeenCalledWith({ parent: "other" });
  expect(state.mutate).toHaveBeenCalled();
});

it("collapses and expands descendants from the pages list", async () => {
  await act(async () => root.render(<PagesListRoot pageType="public" storeType={"project" as EPageStoreType} />));
  expect(container.querySelector('[data-page="child"]')).not.toBeNull();
  await act(async () => container.querySelector("button")!.click());
  expect(container.querySelector('[data-page="child"]')).toBeNull();
  expect(container.querySelector('[data-page="other"]')).not.toBeNull();
  await act(async () => container.querySelector("button")!.click());
  expect(container.querySelector('[data-page="child"]')).not.toBeNull();
});
