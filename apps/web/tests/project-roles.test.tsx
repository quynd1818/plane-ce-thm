import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { SWRConfig } from "swr";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { RestrictedProjectPanel } from "@/components/project-roles/restricted-panel";
import { ProjectRoleManager } from "@/components/project-roles/manager";
import { WorkspaceRoleBoundary } from "@/components/project-roles/workspace-boundary";

const mocks = vi.hoisted(() => ({
  report: vi.fn(),
  exportReport: vi.fn(),
  issues: vi.fn(),
  update: vi.fn(),
  list: vi.fn(),
  assign: vi.fn(),
  workspace: vi.fn(),
  save: vi.fn(),
  remove: vi.fn(),
  setRoles: vi.fn(),
  pathname: "/w/",
  projectId: undefined as string | undefined,
}));
vi.mock("@/services/issue/worklog.service", () => ({
  WorkLogService: class {
    getProjectReport = mocks.report;
    exportProjectReport = mocks.exportReport;
  },
}));
vi.mock("@/services/project/roles.service", () => ({
  projectRolesService: {
    issues: mocks.issues,
    updateProperties: mocks.update,
    list: mocks.list,
    assign: mocks.assign,
    workspace: mocks.workspace,
    save: mocks.save,
    remove: mocks.remove,
  },
  roleError: () => "Permission denied",
}));
const properties = [
  { id: "p1", name: "Legal", key: "legal", property_type: "text", options: [], is_active: true },
  { id: "p2", name: "Finance", key: "finance", property_type: "number", options: [], is_active: true },
];
vi.mock("@/services/project/customization.service", () => ({
  projectCustomizationService: { listProperties: async () => properties },
}));
vi.mock("@/hooks/store/use-workspace", () => ({ useWorkspace: () => ({ workspaces: {} }) }));
vi.mock("@/hooks/store/user", () => ({
  useUser: () => ({ data: { id: "user" }, signOut: vi.fn() }),
  useUserPermissions: () => ({ setCustomProjectRoles: mocks.setRoles }),
}));
vi.mock("next/navigation", () => ({
  useParams: () => ({ projectId: mocks.projectId }),
  usePathname: () => mocks.pathname,
}));
const accounting = {
  id: "role",
  name: "Accounting",
  is_active: true,
  permissions: ["worklogs.read"],
  property_keys: [],
};
const legal = {
  ...accounting,
  name: "Legal",
  permissions: ["properties.read", "properties.edit"],
  property_keys: ["legal"],
};
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.clearAllMocks();
  mocks.projectId = undefined;
  mocks.report.mockResolvedValue({ results: [], total_seconds: 0 });
  mocks.issues.mockResolvedValue({
    count: 1,
    results: [{ id: "issue", sequence_id: 1, name: "Contract", custom_properties: { legal: "pending", finance: 100 } }],
    properties,
  });
  mocks.update.mockResolvedValue({});
  mocks.assign.mockResolvedValue({});
  mocks.list.mockResolvedValue({
    roles: [accounting],
    capabilities: { "worklogs.read": "View worklogs", "worklogs.export": "Export worklogs" },
    members: [{ id: "member", name: "Person", eligible: true, custom_role_id: null }],
  });
  mocks.workspace.mockResolvedValue({
    restricted: true,
    projects: [{ id: "project", name: "Project", role: accounting }],
  });
  container = document.createElement("div");
  document.body.appendChild(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});
const render = async (node: React.ReactNode) => {
  await act(async () => {
    root.render(
      <SWRConfig value={{ provider: () => new Map(), dedupingInterval: 0, shouldRetryOnError: false }}>
        {node}
      </SWRConfig>
    );
  });
  await act(async () => {
    await new Promise((resolve) => setTimeout(resolve, 20));
  });
};
it("read-only accounting can see reports but not export or edit controls", async () => {
  await render(<RestrictedProjectPanel workspaceSlug="w" projectId="p" role={accounting} />);
  expect(container.textContent).toContain("No worklogs");
  expect(container.textContent).not.toContain("Export CSV");
  expect(mocks.issues).not.toHaveBeenCalled();
});
it("export is visible only when separately granted", async () => {
  await render(
    <RestrictedProjectPanel
      workspaceSlug="w"
      projectId="p"
      role={{ ...accounting, permissions: ["worklogs.read", "worklogs.export"] }}
    />
  );
  expect(container.textContent).toContain("Export CSV");
});
it("legal can edit only the granted property and submits only that key", async () => {
  await render(<RestrictedProjectPanel workspaceSlug="w" projectId="p" role={legal} />);
  const inputs = container.querySelectorAll("article input");
  expect(inputs.length).toBe(1);
  expect(container.querySelector("article")?.textContent).toContain("Finance: 100");
  await act(async () => (container.querySelector("article button") as HTMLButtonElement).click());
  expect(mocks.update).toHaveBeenCalledWith("w", "p", "issue", { legal: "pending" });
  expect(mocks.report).not.toHaveBeenCalled();
});
it("failed property saves stay visible and expose an error", async () => {
  mocks.update.mockRejectedValue(new Error("denied"));
  await render(<RestrictedProjectPanel workspaceSlug="w" projectId="p" role={legal} />);
  await act(async () => (container.querySelector("article button") as HTMLButtonElement).click());
  expect(container.querySelector('[role="alert"]')?.textContent).toBe("Permission denied");
  expect((container.querySelector("article input") as HTMLInputElement).value).toBe("pending");
});
it("disabled roles cannot mount data fetchers", async () => {
  await render(<RestrictedProjectPanel workspaceSlug="w" projectId="p" role={{ ...legal, is_active: false }} />);
  expect(container.textContent).toContain("grants no access");
  expect(mocks.issues).not.toHaveBeenCalled();
  expect(mocks.report).not.toHaveBeenCalled();
});
it("administrators can assign an existing role", async () => {
  await render(<ProjectRoleManager workspaceSlug="w" projectId="p" />);
  const select = container.querySelector('select[aria-label="Role for Person"]') as HTMLSelectElement;
  await act(async () => {
    select.value = "role";
    select.dispatchEvent(new Event("change", { bubbles: true }));
  });
  expect(mocks.assign).toHaveBeenCalledWith("w", "p", "member", "role");
});
it("workspace remains accessible when a project has a custom role", async () => {
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Secret aggregate</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Secret aggregate");
  expect(mocks.setRoles).toHaveBeenCalledWith("w", { project: accounting });
});
it("network failures never block the workspace (the API enforces roles itself)", async () => {
  mocks.workspace.mockRejectedValue(new Error("network"));
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Workspace content</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Workspace content");
});
it("projects without custom roles retain built-in access", async () => {
  mocks.projectId = "other";
  mocks.workspace.mockResolvedValue({ restricted: true, projects: [{ id: "other", name: "Other", role: null }] });
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Built-in access</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Built-in access");
});

it("permission dependencies stay consistent when a read grant is removed", async () => {
  mocks.save.mockResolvedValue({});
  await render(<ProjectRoleManager workspaceSlug="w" projectId="p" />);
  const preset = [...container.querySelectorAll("button")].find(
    (button) => button.textContent === "Accounting preset"
  )!;
  await act(async () => preset.click());
  const read = [...container.querySelectorAll("label")]
    .find((label) => label.textContent === "View worklogs")
    ?.querySelector("input");
  if (!read) throw new Error("Missing worklog read permission checkbox");
  await act(async () => read.click());
  await act(async () =>
    container.querySelector("form")!.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }))
  );
  expect(mocks.save).toHaveBeenCalledWith(
    "w",
    "p",
    { name: "Accounting", permissions: [], property_keys: [], is_active: true },
    undefined
  );
});

it("users without custom roles keep their workspace content", async () => {
  mocks.workspace.mockResolvedValue({ restricted: false, projects: [] });
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Regular workspace</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Regular workspace");
  expect(container.textContent).not.toContain("Project access");
});

it("assigned accounting projects use their focused panel", async () => {
  mocks.projectId = "project";
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Normal project</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Project access");
  expect(container.textContent).not.toContain("Normal project");
});

it("expanded roles can mount permitted CE features", async () => {
  mocks.projectId = "project";
  mocks.pathname = "/w/projects/project/issues/";
  mocks.workspace.mockResolvedValue({
    restricted: true,
    projects: [{ id: "project", name: "Project", role: { ...accounting, permissions: ["issues.read"] } }],
  });
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Work items</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Work items");
  expect(container.textContent).not.toContain("Access not granted");
});

it("expanded roles cannot mount a feature without its read permission", async () => {
  mocks.projectId = "project";
  mocks.pathname = "/w/projects/project/pages/";
  mocks.workspace.mockResolvedValue({
    restricted: true,
    projects: [{ id: "project", name: "Project", role: { ...accounting, permissions: ["issues.read"] } }],
  });
  await render(
    <WorkspaceRoleBoundary workspaceSlug="w">
      <div>Page fetcher</div>
    </WorkspaceRoleBoundary>
  );
  expect(container.textContent).toContain("Access not granted");
  expect(container.textContent).not.toContain("Page fetcher");
});
