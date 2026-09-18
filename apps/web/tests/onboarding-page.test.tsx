import { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { SWRConfig, type Cache } from "swr";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import OnboardingPage from "@/app/(all)/onboarding/page";

const state = vi.hoisted(() => ({
  user: { data: undefined as { id: string } | undefined },
  fetchWorkspaces: vi.fn(),
  invitations: vi.fn(),
}));
vi.mock("@plane/constants", () => ({ USER_WORKSPACES_LIST: "workspaces" }));
vi.mock("@/hooks/store/user", () => ({ useUser: () => state.user }));
vi.mock("@/hooks/store/use-workspace", () => ({ useWorkspace: () => state }));
vi.mock("@/services/workspace.service", () => ({
  WorkspaceService: class {
    userWorkspaceInvitations = state.invitations;
  },
}));
vi.mock("@/components/common/logo-spinner", () => ({ LogoSpinner: () => <div role="status">Loading</div> }));
vi.mock("@/components/thm", () => ({ ThmBrandPanel: () => null }));
vi.mock("@/components/onboarding", () => ({ OnboardingRoot: () => <div>Onboarding ready</div> }));
vi.mock("@/helpers/authentication.helper", () => ({ EPageTypes: { ONBOARDING: "ONBOARDING" } }));
vi.mock("@/lib/wrappers/authentication-wrapper", () => ({
  AuthenticationWrapper: ({ children }: { children: React.ReactNode }) => children,
}));

let root: Root;
let container: HTMLDivElement;
let cache: Cache;
beforeEach(() => {
  vi.stubGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  vi.resetAllMocks();
  state.user.data = undefined;
  container = document.createElement("div");
  root = createRoot(container);
  cache = new Map();
});
afterEach(async () => {
  await act(async () => root.unmount());
  vi.unstubAllGlobals();
});
const render = async () => {
  await act(async () =>
    root.render(
      <SWRConfig value={{ provider: () => cache, shouldRetryOnError: false }}>
        <OnboardingPage />
      </SWRConfig>
    )
  );
};

it("fetches when authentication becomes ready and waits for workspace membership", async () => {
  let resolve!: (workspaces: unknown[]) => void;
  state.fetchWorkspaces.mockReturnValue(
    new Promise((done) => {
      resolve = done;
    })
  );
  state.invitations.mockResolvedValue([]);
  await render();
  expect(state.fetchWorkspaces).not.toHaveBeenCalled();
  state.user.data = { id: "sso-user" };
  await render();
  expect(state.fetchWorkspaces).toHaveBeenCalledTimes(1);
  expect(container.textContent).toBe("Loading");
  await act(async () => resolve([{ id: "existing-workspace" }]));
  expect(container.textContent).toBe("Onboarding ready");
});

it("does not interpret failed requests as no invitations and supports retry", async () => {
  state.user.data = { id: "sso-user" };
  state.fetchWorkspaces.mockRejectedValueOnce(new Error("offline")).mockResolvedValue([]);
  state.invitations.mockResolvedValue([]);
  await render();
  expect(container.querySelector('[role="alert"]')).not.toBeNull();
  expect(container.textContent).not.toContain("Onboarding ready");
  await act(async () => container.querySelector("button")!.click());
  expect(container.textContent).toBe("Onboarding ready");
});

it("loads fresh membership data when the account changes", async () => {
  state.user.data = { id: "first" };
  state.fetchWorkspaces.mockResolvedValue([]);
  state.invitations.mockResolvedValue([]);
  await render();
  state.user.data = { id: "second" };
  await render();
  expect(state.fetchWorkspaces).toHaveBeenCalledTimes(2);
  expect(state.invitations).toHaveBeenCalledTimes(2);
});
